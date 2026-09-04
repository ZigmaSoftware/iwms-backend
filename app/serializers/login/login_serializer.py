from rest_framework import serializers
from django.contrib.auth.hashers import check_password, identify_hasher
from django.db.models import F, Q
from django.utils import timezone

from app.models.staff_creations.staffcreation import Staffcreation
from app.models.customers.customercreation import CustomerCreation
from app.models.customers.customer_access_configuration import CustomerAccessConfiguration
from app.models.role_assigns.userType import UserType
from app.models.superadmin_masters.auth_user import User
from app.models.masters.panchayat_leader_login import PanchayatLeaderLogin
from app.models.masters.district_leader_login import DistrictLeaderLogin

from app.models.superadmin_masters.project import Project
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.staff_creations.staff_access_configuration import StaffAccessConfiguration
from app.utils.permission_response import (
    finalize_permission_payload,
    resolve_permission_payload,
)
from app.utils.password_encryption import decrypt_password

PASSWORD_EXPIRY_DAYS = 90


def _is_password_expired(password_crt_date):
    """Return True if the password is older than PASSWORD_EXPIRY_DAYS days."""
    if not password_crt_date:
        return False
    age = timezone.now() - password_crt_date
    return age.days >= PASSWORD_EXPIRY_DAYS


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    login_type = serializers.ChoiceField(
        choices=["auto", "staff", "customer", "platform", "contractor", "panchayat_leader", "district_member"],
        default="auto",
        required=False
    )
    # The mobile app identifies itself so the App Module gate applies to it and
    # not to web. Absent (or "web") means a browser sign-in, which is never
    # gated on an app module — a web-only admin has no reason to hold one.
    client = serializers.CharField(required=False, allow_blank=True, default="web")

    @staticmethod
    def _password_matches(raw_password, stored_password):
        if stored_password is None:
            return False
        try:
            identify_hasher(stored_password)
        except ValueError:
            decrypted_password = decrypt_password(stored_password)
            if decrypted_password:
                return raw_password == decrypted_password
            return raw_password == stored_password
        return check_password(raw_password, stored_password)

    def _determine_order(self, login_type):
        if login_type == "staff":
            return ["staff", "customer", "platform"]
        if login_type == "customer":
            return ["customer", "staff", "platform"]
        if login_type == "platform":
            return ["platform"]
        if login_type == "contractor":
            return ["contractor", "staff", "customer", "platform"]
        if login_type == "panchayat_leader":
            return ["panchayat_leader"]
        if login_type == "district_member":
            return ["district_member"]
        return ["customer", "staff", "platform", "contractor"]

    def _format_permissions(self, queryset):
        permissions = {}
        for perm in queryset.order_by("order_no"):
            main_name = perm.mainscreen_id.mainscreen_name
            screen_name = perm.userscreen_id.userscreen_name
            action_name = perm.userscreenaction_id.action_name

            screen_map = permissions.setdefault(main_name, {})
            actions = screen_map.setdefault(screen_name, [])
            if action_name not in actions:
                actions.append(action_name)

        return permissions

    def _resolve_permission_payload(
        self,
        *,
        company_unique_id=None,
        staff_unique_id=None,
        include_all=False,
        role_name=None,
        user_type=None,
        app_module=None,
        app_modules=None,
        citizen_screens=None,
    ):
        return resolve_permission_payload(
            company_unique_id=company_unique_id,
            staff_unique_id=staff_unique_id,
            include_all=include_all,
            role_name=role_name,
            user_type=user_type,
            app_module=app_module,
            app_modules=app_modules,
            citizen_screens=citizen_screens,
        )

    def _resolve_permissions(
        self,
        *,
        company_unique_id=None,
        staff_unique_id=None,
        include_all=False
    ):
        payload = self._resolve_permission_payload(
            company_unique_id=company_unique_id,
            staff_unique_id=staff_unique_id,
            include_all=include_all,
        )
        return payload["permissions"]

    def _resolve_location_scope(self, access_config, company, project_ids):
        """Mirror the company/project scoping convention for the geo levels:
        an empty selection on StaffAccessConfiguration means "unrestricted"
        at that level (every record under the resolved parent scope),
        while an explicit selection restricts to just those records.

        Each level narrows the next: states -> districts -> cities ->
        wards, all additionally scoped to the resolved company (and
        project(s), where applicable). Zone/Panchayat are the exception —
        see the comment at their resolution below.
        """
        base_project_filter = {"project_id_id__in": project_ids} if project_ids else {}

        scoped_states = access_config.states.all() if access_config else State.objects.none()
        if scoped_states.exists():
            states_qs = scoped_states
        else:
            states_qs = State.objects.filter(is_deleted=False)
        state_ids = list(states_qs.values_list("unique_id", flat=True))

        scoped_districts = access_config.districts.all() if access_config else District.objects.none()
        if scoped_districts.exists():
            districts_qs = scoped_districts
        else:
            districts_qs = District.objects.filter(
                company_id=company, is_deleted=False, state_id_id__in=state_ids, **base_project_filter
            )
        district_ids = list(districts_qs.values_list("unique_id", flat=True))

        scoped_cities = access_config.cities.all() if access_config else City.objects.none()
        if scoped_cities.exists():
            cities_qs = scoped_cities
        else:
            cities_qs = City.objects.filter(
                company_id=company, is_deleted=False, district_id_id__in=district_ids, **base_project_filter
            )
        city_ids = list(cities_qs.values_list("unique_id", flat=True))

        # Zone and Panchayat are mutually-independent siblings under City,
        # not a strict narrowing chain like state->district->city->ward: a
        # staff may be assigned one, the other, both, or neither. So unlike
        # the other levels, an empty selection here does NOT fall back to
        # "every zone/panchayat under the city" — that would silently grant
        # a level Super Admin never assigned. The unrestricted-parent
        # fallback only applies when there's no access config at all (e.g.
        # legacy staff with no Data Scope configured yet).
        if access_config:
            zones_qs = access_config.zones.all()
            panchayats_qs = access_config.panchayats.all()
        else:
            zones_qs = Zone.objects.filter(
                company_id=company, is_deleted=False, city_id_id__in=city_ids, **base_project_filter
            )
            panchayats_qs = Panchayat.objects.filter(
                company_id=company, is_deleted=False, city_id_id__in=city_ids, **base_project_filter
            )

        scoped_wards = access_config.wards.all() if access_config else Ward.objects.none()
        if scoped_wards.exists():
            wards_qs = scoped_wards
        else:
            wards_qs = Ward.objects.filter(
                company_id=company, is_deleted=False, city_id_id__in=city_ids, **base_project_filter
            )

        # Continent/Country are not independently assignable — they're
        # derived from whichever states are in scope, same as the
        # StaffAccessConfigurationSerializer admin API already does.
        continents = {}
        countries = {}
        for state in states_qs.select_related("continent_id", "country_id"):
            if state.continent_id and state.continent_id.unique_id not in continents:
                continents[state.continent_id.unique_id] = state.continent_id.name
            if state.country_id and state.country_id.unique_id not in countries:
                countries[state.country_id.unique_id] = state.country_id.name

        # The narrowest level the admin actually assigned a grant at, in the
        # same narrowest-to-broadest order the rest of this method resolves
        # in. Zone/Panchayat are siblings (see comment above) so either one
        # being assigned counts as "ward"-adjacent granularity; whichever of
        # the two was actually granted is reported. "company" means no
        # geo-level grant at all — unrestricted down to the whole company.
        scope_level = "company"
        if access_config:
            if scoped_wards.exists():
                scope_level = "ward"
            elif access_config.zones.exists():
                scope_level = "zone"
            elif access_config.panchayats.exists():
                scope_level = "panchayat"
            elif scoped_cities.exists():
                scope_level = "city"
            elif scoped_districts.exists():
                scope_level = "district"
            elif scoped_states.exists():
                scope_level = "state"

        return {
            "scope_level": scope_level,
            "continents": [{"unique_id": k, "name": v} for k, v in continents.items()],
            "countries": [{"unique_id": k, "name": v} for k, v in countries.items()],
            "states": list(states_qs.values("unique_id", "name")),
            "districts": list(districts_qs.values("unique_id", "name")),
            "cities": list(cities_qs.values("unique_id", "name")),
            "zones": list(zones_qs.values("unique_id", "zone_name")),
            "panchayats": list(panchayats_qs.values("unique_id", "panchayat_name")),
            "wards": list(wards_qs.values("unique_id", "ward_name")),
        }

    def _build_staff_payload(self, staff_record, login_user=None):
        login_user = login_user or staff_record

        if not staff_record.login_enabled:
            Staffcreation.objects.filter(pk=staff_record.pk).update(
                failed_login_attempts=F("failed_login_attempts") + 1
            )
            raise serializers.ValidationError("Login is disabled for this user")

        user_type = staff_record.user_type_id or getattr(login_user, "user_type_id", None)
        if not user_type:
            raise serializers.ValidationError("Invalid user type")

        allowed_roles = ["staff", "contractor"]

        if user_type.name.lower() not in allowed_roles:
            raise serializers.ValidationError("Unsupported user role type")

        staff_usertype = getattr(staff_record, "staffusertype_id", None) or getattr(login_user, "staffusertype_id", None)
        contractor_usertype = getattr(staff_record, "contractorusertype_id", None) or getattr(login_user, "contractorusertype_id", None)
        role_usertype = staff_usertype or contractor_usertype

        if not role_usertype:
            raise serializers.ValidationError("Staff role not assigned")

        # Staff Access Configuration (the "Data Scope" tab) is the source of
        # truth for which company/projects/locations a staff can operate
        # under, once one exists for them — it supports multiple projects
        # and treats an empty selection at any level (project, state,
        # district, city, zone, panchayat, ward) as "everything under the
        # parent scope". Forms should show company/project/location data
        # from this scope regardless of whether the staff was separately
        # granted "view" on those as screens — that permission only governs
        # the admin management screens' own sidebar visibility.
        access_config = StaffAccessConfiguration.objects.filter(
            staff_id_id=getattr(staff_record, "staff_unique_id", None),
            is_active=True,
            is_deleted=False,
        ).select_related("company_id").prefetch_related(
            "projects", "states", "districts", "cities", "zones", "panchayats", "wards",
        ).first()

        if access_config and access_config.company_id:
            company = access_config.company_id
            scoped_projects = access_config.projects.all()
            project_filter = {"company_id": company, "is_active": True, "is_deleted": False}
            if scoped_projects.exists():
                project_filter["unique_id__in"] = list(scoped_projects.values_list("unique_id", flat=True))
        else:
            company = getattr(staff_record, "company_id", None) or getattr(login_user, "company_id", None)
            if not company:
                raise serializers.ValidationError("Staff record has no company assigned")

            project_filter = {"company_id": company, "is_active": True, "is_deleted": False}
            staff_project = getattr(staff_record, "project_id", None)
            if staff_project:
                project_filter["unique_id"] = getattr(staff_project, "unique_id", staff_project)

        projects_queryset = Project.objects.filter(**project_filter).values(
            "unique_id", "name",
            "gps_api_url",
            "gps_vehicle_history_api", "gps_vehicle_tracking_api", "gps_trip_summary_api",
            "gps_user_id", "gps_group_name", "gps_provider_name", "gps_fcode", "gps_trip_user_id",
            "weighment_api_url", "day_wise_weighment_api_url",
        )

        projects = list(projects_queryset)
        resolved_project_ids = [p["unique_id"] for p in projects]
        location_scope = self._resolve_location_scope(access_config, company, resolved_project_ids)

        permission_payload = self._resolve_permission_payload(
            company_unique_id=company.unique_id,
            staff_unique_id=getattr(staff_record, "staff_unique_id", None),
            role_name=role_usertype.name,
            user_type="contractor" if contractor_usertype else "staff",
            app_module=getattr(staff_record, "app_module", None),
        )
        # resolve_permission_payload already applies the role baseline as a
        # floor (unless the staff member is in strict mode), so there is no
        # second, divergent copy of that logic here any more.
        permissions = permission_payload["permissions"]

        password_expired = _is_password_expired(getattr(staff_record, "password_crt_date", None))

        profile_payload = {
            "staff_unique_id": getattr(staff_record, "staff_unique_id", None),
            "employee_name": getattr(staff_record, "employee_name", None),
            "district_unique_id": getattr(getattr(staff_record, "district_id", None), "unique_id", None),
            "district_name": getattr(getattr(staff_record, "district_id", None), "name", None),
        }

        return {
            "user": login_user,
            "permissions": permissions,
            "permission_details": permission_payload["permission_details"],
            "column_permissions": permission_payload["column_permissions"],
            "module_access": permission_payload["module_access"],
            "app_surfaces": permission_payload["app_surfaces"],
            "landing": permission_payload["landing"],
            "app_modules": permission_payload.get("app_modules", []),
            "app_screens": permission_payload.get("app_screens", {}),
            "permission_version": permission_payload["permission_version"],
            "generated_at": permission_payload["generated_at"],
            "user_type": "contractor" if contractor_usertype else "staff",
            "staffusertype_id": staff_usertype.unique_id if staff_usertype else None,
            "contractorusertype_id": contractor_usertype.unique_id if contractor_usertype else None,
            "company_unique_id": company.unique_id,
            "projects": projects,
            "scope_level": location_scope["scope_level"],
            "continents": location_scope["continents"],
            "countries": location_scope["countries"],
            "states": location_scope["states"],
            "districts": location_scope["districts"],
            "cities": location_scope["cities"],
            "zones": location_scope["zones"],
            "panchayats": location_scope["panchayats"],
            "wards": location_scope["wards"],
            "profile_object": staff_record,
            "profile": profile_payload,
            "password_expired": password_expired,
        }

    def _build_district_payload(self, staff_record, login_user=None):
        payload = self._build_staff_payload(staff_record, login_user=login_user)
        payload["user_type"] = "district_member"
        return payload

    def _build_customer_payload(self, customer_record, login_user=None):
        login_user = login_user or customer_record

        user_type = customer_record.user_type_id or getattr(login_user, "user_type_id", None)
        if not user_type:
            user_type = UserType.objects.filter(name__iexact="customer").first()
        if not user_type:
            raise serializers.ValidationError("Customer user type is not configured")

        company = getattr(customer_record, "company_id", None) or getattr(login_user, "company_id", None)
        if not company:
            raise serializers.ValidationError("Customer record has no company assigned")

        # Customers are not scoped through Staff Access Configuration — they
        # have no staff record to hang one off. A Customer Access
        # Configuration is the strict source when it exists; until one is
        # backfilled, the customer's app_module keeps legacy citizen logins
        # working and all citizen screens remain visible.
        access_config = (
            CustomerAccessConfiguration.objects
            .filter(customer_id_id=customer_record.unique_id, is_deleted=False, is_active=True)
            .prefetch_related("app_modules", "app_screens")
            .first()
        )
        customer_modules = (
            list(
                access_config.app_modules.filter(is_active=True, is_deleted=False)
                .values_list("surface_key", flat=True)
            )
            if access_config
            else None
        )
        citizen_screens = (
            set(
                access_config.app_screens.filter(is_active=True, is_deleted=False)
                .values_list("userscreen_name", flat=True)
            )
            if access_config
            else None
        )

        permission_payload = self._resolve_permission_payload(
            company_unique_id=company.unique_id,
            role_name="customer",
            user_type="customer",
            app_module=getattr(customer_record, "app_module", None) or "citizen",
            app_modules=customer_modules,
            citizen_screens=citizen_screens,
        )
        permissions = permission_payload["permissions"]

        password_expired = _is_password_expired(getattr(customer_record, "password_crt_date", None))

        return {
            "user": login_user,
            "permissions": permissions,
            "permission_details": permission_payload["permission_details"],
            "column_permissions": permission_payload["column_permissions"],
            "module_access": permission_payload["module_access"],
            "app_surfaces": permission_payload["app_surfaces"],
            "landing": permission_payload["landing"],
            "app_modules": permission_payload.get("app_modules", []),
            "app_screens": permission_payload.get("app_screens", {}),
            "permission_version": permission_payload["permission_version"],
            "generated_at": permission_payload["generated_at"],
            "user_type": "customer",
            "staffusertype_id": None,
            "company_unique_id": company.unique_id,
            "profile_object": customer_record,
            "password_expired": password_expired,
        }

    def _build_platform_payload(self, user):
        permission_payload = self._resolve_permission_payload(
            include_all=True,
            role_name="superadmin",
            user_type="platform",
        )
        permissions = permission_payload["permissions"]

        return {
            "user": user,
            "permissions": permissions,
            "permission_details": permission_payload["permission_details"],
            "column_permissions": permission_payload["column_permissions"],
            "module_access": permission_payload["module_access"],
            "app_surfaces": permission_payload["app_surfaces"],
            "landing": permission_payload["landing"],
            "app_modules": permission_payload.get("app_modules", []),
            "app_screens": permission_payload.get("app_screens", {}),
            "permission_version": permission_payload["permission_version"],
            "generated_at": permission_payload["generated_at"],
            "user_type": "platform",
            "staffusertype_id": getattr(getattr(user, "staffusertype_id", None), "unique_id", None),
            "company_unique_id": getattr(getattr(user, "company_id", None), "unique_id", None),
        }

    def _authenticate_customer(self, username, password):
        candidates = (
            CustomerCreation.objects
            .filter(is_active=True, is_deleted=False)
            .filter(
                Q(username__iexact=username) |
                Q(customer_name__iexact=username) |
                Q(contact_no__iexact=username)
            )
        )

        for candidate in candidates:
            if not self._password_matches(password, candidate.password):
                continue

            return self._build_customer_payload(candidate)

        return None

    def _authenticate_staff(self, username, password):
        lookup_filters = (
            Q(employee_name__iexact=username) |
            Q(username__iexact=username) |
            Q(emp_id__iexact=username)
        )

        queryset = (
            Staffcreation.objects
            .select_related("user_type_id", "staffusertype_id", "contractorusertype_id", "personal_details", "company_id")
            .filter(is_active=True, is_deleted=False)
            .filter(lookup_filters)
        )

        for candidate in queryset:
            if not self._password_matches(password, candidate.password):
                Staffcreation.objects.filter(pk=candidate.pk).update(
                    failed_login_attempts=F("failed_login_attempts") + 1
                )
                continue

            if candidate.is_superuser and not candidate.company_id:
                # Platform super admins live in a different table/path.
                return None

            if not candidate.login_enabled:
                Staffcreation.objects.filter(pk=candidate.pk).update(
                    failed_login_attempts=F("failed_login_attempts") + 1
                )
                raise serializers.ValidationError("Login is disabled for this user")

            return self._build_staff_payload(candidate)

        return None

    def _authenticate_district_member(self, username, password):
        leader = (
            DistrictLeaderLogin.objects
            .select_related("district_id", "company_id", "project_id")
            .filter(is_active=True, is_deleted=False)
            .filter(Q(username__iexact=username) | Q(email__iexact=username))
            .first()
        )

        if leader:
            if not self._password_matches(password, leader.password):
                return None
            return self._build_district_leader_payload(leader)

        lookup_filters = (
            Q(employee_name__iexact=username) |
            Q(username__iexact=username) |
            Q(emp_id__iexact=username)
        )

        queryset = (
            Staffcreation.objects
            .select_related("user_type_id", "staffusertype_id", "contractorusertype_id", "personal_details", "company_id", "district_id")
            .filter(is_active=True, is_deleted=False)
            .filter(district_id__isnull=False)
            .filter(lookup_filters)
        )

        for candidate in queryset:
            if not self._password_matches(password, candidate.password):
                Staffcreation.objects.filter(pk=candidate.pk).update(
                    failed_login_attempts=F("failed_login_attempts") + 1
                )
                continue

            if candidate.is_superuser and not candidate.company_id:
                return None

            return self._build_district_payload(candidate)

        return None

    def _build_district_leader_payload(self, leader):
        district = leader.district_id
        company = leader.company_id or (district.company_id if district else None)
        project = leader.project_id or (district.project_id if district else None)

        projects = []
        if project:
            projects = [{
                "unique_id": project.unique_id,
                "name": project.name,
                "gps_api_url": getattr(project, "gps_api_url", None),
                "gps_vehicle_history_api": getattr(project, "gps_vehicle_history_api", None),
                "gps_vehicle_tracking_api": getattr(project, "gps_vehicle_tracking_api", None),
                "gps_trip_summary_api": getattr(project, "gps_trip_summary_api", None),
                "weighment_api_url": getattr(project, "weighment_api_url", None),
            }]
        elif company:
            projects = list(
                Project.objects.filter(
                    company_id=company,
                    is_active=True,
                    is_deleted=False,
                ).values(
                    "unique_id", "name", "gps_api_url",
                    "gps_vehicle_history_api", "gps_vehicle_tracking_api", "gps_trip_summary_api",
                    "weighment_api_url",
                )
            )

        return {
            "user": leader,
            "permissions": {},
            "permission_details": {},
            "column_permissions": {},
            "module_access": [],
            "app_surfaces": [],
            "landing": None,
            "permission_version": None,
            "generated_at": None,
            "user_type": "district_member",
            "staffusertype_id": None,
            "contractorusertype_id": None,
            "company_unique_id": company.unique_id if company else None,
            "projects": projects,
            "profile_object": leader,
            "password_expired": False,
        }

    def _authenticate_platform(self, username, password):
        user = (
            User.objects
            .select_related(
                "staff_id__user_type_id",
                "staff_id__staffusertype_id",
                "staff_id__contractorusertype_id",
                "staff_id__company_id",
                "customer_id__user_type_id",
                "customer_id__company_id",
                "user_type_id",
                "staffusertype_id",
                "company_id",
            )
            .filter(username__iexact=username, is_active=True, is_deleted=False)
            .first()
        )

        if not user or not self._password_matches(password, user.password):
            return None

        staff_record = getattr(user, "staff_id", None)
        if staff_record:
            if staff_record.is_superuser and not getattr(staff_record, "company_id", None):
                return self._build_platform_payload(user)
            return self._build_staff_payload(staff_record, login_user=user)

        customer_record = getattr(user, "customer_id", None)
        if customer_record:
            return self._build_customer_payload(customer_record, login_user=user)

        if user.is_superuser:
            return self._build_platform_payload(user)

        return None

    def _build_panchayat_leader_payload(self, leader):
        panchayat = leader.panchayat_id
        company = leader.company_id or (panchayat.company_id if panchayat else None)
        project = leader.project_id or (panchayat.project_id if panchayat else None)

        return {
            "user": leader,
            "permissions": {},
            "permission_details": {},
            "column_permissions": {},
            "module_access": [],
            "app_surfaces": [],
            "landing": None,
            "permission_version": None,
            "generated_at": None,
            "user_type": "panchayat_leader",
            "staffusertype_id": None,
            "contractorusertype_id": None,
            "company_unique_id": company.unique_id if company else None,
            "projects": [],
            "profile_object": leader,
        }

    def _authenticate_panchayat_leader(self, username, password):
        leader = (
            PanchayatLeaderLogin.objects
            .select_related("panchayat_id", "company_id", "project_id")
            .filter(is_active=True, is_deleted=False)
            .filter(Q(username__iexact=username) | Q(email__iexact=username))
            .first()
        )

        if not leader:
            return None

        if not self._password_matches(password, leader.password):
            return None

        return self._build_panchayat_leader_payload(leader)

    @staticmethod
    def _is_mobile_client(attrs):
        return str(attrs.get("client") or "web").strip().lower() in {
            "mobile", "app", "android", "ios",
        }

    def _enforce_app_module_gate(self, attrs, data):
        """Refuse a mobile sign-in for someone with no App Module ticked.

        Web sign-in is untouched: the gate is about which app a person may
        open, and a browser is not one of them.
        """
        if not self._is_mobile_client(attrs):
            return

        if data.get("app_modules"):
            return

        raise serializers.ValidationError(
            "This account has no mobile app access. Ask your administrator to "
            "tick an App Module for you in Staff Access Configuration."
        )

    def validate(self, attrs):
        username = attrs["username"].strip()
        password = attrs["password"].strip()
        login_type = attrs.get("login_type", "auto")

        first_error = None
        for provider in self._determine_order(login_type):
            authenticate_method = getattr(self, f"_authenticate_{provider}", None)
            if not authenticate_method:
                continue
            try:
                data = authenticate_method(username, password)
            except serializers.ValidationError as exc:
                if first_error is None:
                    first_error = exc
                continue
            if data:
                self._enforce_app_module_gate(attrs, data)
                attrs.update(data)
                return attrs

        if first_error:
            raise first_error

        raise serializers.ValidationError("Invalid username or password")
