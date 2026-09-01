from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from app.models.common_masters.state import State
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.screen_managements.companyuserscreenpermission import (
    CompanyUserScreenPermission,
)
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.user_creations.staff_access_configuration import (
    StaffAccessConfiguration,
    StaffAccessConfigurationPermission,
)
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails
from app.serializers.superadmin.staff_management.staffcreation_serializer import StaffcreationSerializer


# (write-payload key, model, m2m accessor name on StaffAccessConfiguration, is geo-scoped-to-project)
LOCATION_LEVELS = (
    ("state_ids", State, "states", False),
    ("district_ids", District, "districts", True),
    ("city_ids", City, "cities", True),
    ("zone_ids", Zone, "zones", True),
    ("panchayat_ids", Panchayat, "panchayats", True),
    ("ward_ids", Ward, "wards", True),
)


def _project_enabled_screen_action_keys(company_id, project_ids):
    """(userscreen_id, userscreenaction_id) pairs enabled for the given
    projects' catalogs. `project_ids` falsy/empty means "no project
    restriction" — i.e. the staff is scoped to the whole company, so the
    catalog is the company-level (project_id IS NULL) permissions only."""
    qs = CompanyUserScreenPermission.objects.filter(
        company_id_id=company_id,
        permission_type="screen",
        is_deleted=False,
        is_active=True,
    )
    if project_ids:
        qs = qs.filter(project_id_id__in=project_ids)
    else:
        qs = qs.filter(project_id__isnull=True)
    qs = qs.exclude(
        Q(userscreenaction_id__action_name__iexact="show")
        | Q(userscreenaction_id__variable_name__iexact="show")
    ).values_list("userscreen_id_id", "userscreenaction_id_id", "mainscreen_id_id")
    return {(row[0], row[1]): row[2] for row in qs}


class StaffAccessConfigurationPermissionInputSerializer(serializers.Serializer):
    userscreen_id = serializers.CharField(required=False)
    userScreenId = serializers.CharField(required=False)
    action_ids = serializers.ListField(child=serializers.CharField(), required=False)
    actionIds = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, data):
        data["userscreen_id"] = data.get("userscreen_id") or data.get("userScreenId")
        data["action_ids"] = data.get("action_ids") or data.get("actionIds") or []
        if not data["userscreen_id"]:
            raise serializers.ValidationError({"userscreen_id": "This field is required."})
        return data


class StaffAccessConfigurationSerializer(serializers.ModelSerializer):
    staff_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    company_id = serializers.CharField()
    project_ids = serializers.ListField(child=serializers.CharField(), required=False)

    state_ids = serializers.ListField(child=serializers.CharField(), required=False)
    district_ids = serializers.ListField(child=serializers.CharField(), required=False)
    city_ids = serializers.ListField(child=serializers.CharField(), required=False)
    zone_ids = serializers.ListField(child=serializers.CharField(), required=False)
    panchayat_ids = serializers.ListField(child=serializers.CharField(), required=False)
    ward_ids = serializers.ListField(child=serializers.CharField(), required=False)

    permissions = StaffAccessConfigurationPermissionInputSerializer(many=True, required=False, write_only=True)
    basicInfo = serializers.JSONField(required=False, write_only=True)
    loginConfig = serializers.JSONField(required=False, write_only=True)
    dataScope = serializers.JSONField(required=False, write_only=True)

    staff_name = serializers.CharField(source="staff_id.employee_name", read_only=True)
    username = serializers.CharField(source="staff_id.username", read_only=True, default=None)
    employee_name = serializers.CharField(source="staff_id.employee_name", read_only=True)
    contact_mobile = serializers.CharField(source="staff_id.personal_details.contact_mobile", read_only=True, default=None)
    contact_email = serializers.CharField(source="staff_id.personal_details.contact_email", read_only=True, default=None)
    doj = serializers.DateField(source="staff_id.doj", read_only=True, default=None)
    user_type_id = serializers.CharField(source="staff_id.user_type_id_id", read_only=True, default=None)
    staffusertype_id = serializers.CharField(source="staff_id.staffusertype_id_id", read_only=True, default=None)
    staffusertype_name = serializers.CharField(source="staff_id.staffusertype_id.name", read_only=True, default=None)
    company_name = serializers.CharField(source="company_id.name", read_only=True)

    granted_permissions = serializers.SerializerMethodField()
    main_screen_count = serializers.SerializerMethodField()
    screen_count = serializers.SerializerMethodField()

    class Meta:
        model = StaffAccessConfiguration
        exclude = ("projects", "states", "districts", "cities", "zones", "panchayats", "wards")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["staff_id"] = instance.staff_id_id
        data["staff_unique_id"] = instance.staff_id_id
        data["company_id"] = instance.company_id_id

        data["project_ids"] = list(instance.projects.values_list("unique_id", flat=True))
        data["project_names"] = list(instance.projects.values_list("name", flat=True))

        name_fields = {
            "states": "name",
            "districts": "name",
            "cities": "name",
            "zones": "zone_name",
            "panchayats": "panchayat_name",
            "wards": "ward_name",
        }
        for accessor, name_field in name_fields.items():
            manager = getattr(instance, accessor)
            singular = accessor[:-1] if accessor != "cities" else "city"
            data[f"{singular}_ids"] = list(manager.values_list("unique_id", flat=True))
            data[f"{singular}_names"] = list(manager.values_list(name_field, flat=True))

        continent_ids = []
        continent_names = []
        country_ids = []
        country_names = []
        for state in instance.states.all().select_related("continent_id", "country_id"):
            if state.continent_id:
                c_id = state.continent_id.unique_id
                if c_id not in continent_ids:
                    continent_ids.append(c_id)
                    continent_names.append(state.continent_id.name)
            if state.country_id:
                c_id = state.country_id.unique_id
                if c_id not in country_ids:
                    country_ids.append(c_id)
                    country_names.append(state.country_id.name)
        data["continent_ids"] = continent_ids
        data["continent_names"] = continent_names
        data["country_ids"] = country_ids
        data["country_names"] = country_names

        # Narrowest level actually granted, in the same narrowest-to-broadest
        # order the login-time scope resolution uses. Zone/Panchayat are
        # siblings under City (see StaffAccessConfiguration docs), so either
        # being assigned counts as that granularity. "company" means no
        # geo-level grant at all — unrestricted down to the whole company.
        scope_level = "company"
        if data["ward_ids"]:
            scope_level = "ward"
        elif data["zone_ids"]:
            scope_level = "zone"
        elif data["panchayat_ids"]:
            scope_level = "panchayat"
        elif data["city_ids"]:
            scope_level = "city"
        elif data["district_ids"]:
            scope_level = "district"
        elif data["state_ids"]:
            scope_level = "state"
        data["scope_level"] = scope_level

        if instance.staff_id:
            staff_data = StaffcreationSerializer(instance.staff_id, context=self.context).data
            data["password"] = staff_data.get("password", "")
        return data

    def _nested_value(self, *keys, default=None):
        source = self.initial_data or {}
        for key in keys:
            if isinstance(source, dict) and key in source:
                value = source.get(key)
                if value not in ("", None):
                    return value
        return default

    def _nested_list(self, group, snake_key, camel_key=None):
        source = self.initial_data or {}
        nested = source.get(group) if isinstance(source, dict) else None
        value = None
        if isinstance(nested, dict):
            value = nested.get(camel_key or snake_key) or nested.get(snake_key)
        if value is None:
            value = source.get(snake_key) if isinstance(source, dict) else None
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return []

    def _build_staff_payload(self, staff=None):
        source = self.initial_data or {}
        basic = source.get("basicInfo") if isinstance(source, dict) else {}
        login = source.get("loginConfig") if isinstance(source, dict) else {}
        basic = basic if isinstance(basic, dict) else {}
        login = login if isinstance(login, dict) else {}

        payload = {
            "company_id": self._nested_value("company_id", "companyId"),
            "employee_name": (
                basic.get("employeeName")
                or basic.get("employee_name")
                or source.get("employee_name")
                or source.get("staff_name")
            ),
            "doj": basic.get("doj") or source.get("doj"),
            "username": login.get("username") or source.get("username"),
            "password": login.get("password") or source.get("password"),
            "contact_mobile": basic.get("mobileNumber") or basic.get("contact_mobile") or source.get("contact_mobile"),
            "contact_email": basic.get("officeEmail") or basic.get("contact_email") or source.get("contact_email"),
            "staffusertype_id": (
                login.get("staffUserTypeId")
                or login.get("staffusertype_id")
                or login.get("governmentUserTypeId")
                or source.get("staffusertype_id")
            ),
            "active_status": basic.get("activeStatus", source.get("active_status", True)),
            "login_enabled": login.get("loginEnabled", source.get("login_enabled", True)),
        }

        primary_project_id = self._nested_value("project_id", "projectId")
        if not primary_project_id:
            project_ids = self._nested_list("dataScope", "project_ids", "projectIds") or (
                source.get("project_ids") if isinstance(source, dict) else None
            ) or []
            primary_project_id = project_ids[0] if project_ids else None
        if primary_project_id:
            payload["project_id"] = primary_project_id

        for key in ("department_id", "designation_id"):
            value = basic.get(key) or basic.get(key.replace("_id", "Id")) or source.get(key)
            if value not in ("", None):
                payload[key] = value

        if staff and not payload.get("password"):
            payload.pop("password", None)

        return {key: value for key, value in payload.items() if value not in ("", None)}

    def _save_staff(self, company, project, existing_staff=None):
        payload = self._build_staff_payload(existing_staff)
        if not existing_staff and not payload.get("employee_name"):
            raise serializers.ValidationError({
                "basicInfo": "Employee name is required when creating staff access."
            })
        serializer = StaffcreationSerializer(
            existing_staff,
            data=payload,
            partial=bool(existing_staff),
            context=self.context,
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save(company_id=company, project_id=project)

    def get_granted_permissions(self, obj):
        rows = obj.granted_permissions.filter(is_deleted=False).select_related(
            "mainscreen_id", "userscreen_id", "userscreenaction_id"
        )
        grouped = {}
        for row in rows:
            screen = grouped.setdefault(
                row.userscreen_id_id,
                {
                    "mainScreenId": row.mainscreen_id_id,
                    "mainScreenName": row.mainscreen_id.mainscreen_name,
                    "userScreenId": row.userscreen_id_id,
                    "userScreenName": row.userscreen_id.userscreen_name,
                    "actionIds": [],
                },
            )
            screen["actionIds"].append(row.userscreenaction_id_id)
        return list(grouped.values())

    def get_main_screen_count(self, obj):
        return (
            obj.granted_permissions.filter(is_deleted=False)
            .values("mainscreen_id_id")
            .distinct()
            .count()
        )

    def get_screen_count(self, obj):
        return (
            obj.granted_permissions.filter(is_deleted=False)
            .values("userscreen_id_id")
            .distinct()
            .count()
        )

    def validate(self, data):
        staff_id = data.get("staff_id")
        company_id = data.get("company_id")

        staff = None
        if staff_id:
            try:
                staff = StaffcreationOfficeDetails.objects.get(staff_unique_id=staff_id, is_deleted=False)
            except StaffcreationOfficeDetails.DoesNotExist:
                raise serializers.ValidationError({"staff_id": "Invalid staff"})

        try:
            company = Company.objects.get(unique_id=company_id, is_deleted=False)
        except Company.DoesNotExist:
            raise serializers.ValidationError({"company_id": "Invalid company"})

        # Company is the only mandatory scope field. An empty project_ids list
        # means "no project restriction" — the staff can access every project
        # (and, transitively, every geo record) under the company, including
        # ones added later. Only validate/resolve the projects the caller did
        # list.
        project_ids = data.get("project_ids") or self._nested_list("dataScope", "project_ids", "projectIds")
        project_ids = list(dict.fromkeys(project_ids))

        projects = list(Project.objects.filter(
            unique_id__in=project_ids, company_id_id=company.unique_id, is_deleted=False,
        ))
        found_project_ids = {p.unique_id for p in projects}
        missing = [pid for pid in project_ids if pid not in found_project_ids]
        if missing:
            raise serializers.ValidationError({
                "project_ids": f"Invalid project(s) for company: {', '.join(missing)}"
            })

        resolved_locations = {}
        for field_key, model, accessor, project_scoped in LOCATION_LEVELS:
            ids = data.get(field_key) or self._nested_list(
                "dataScope", field_key, field_key[:-4] + "Ids"
            )
            ids = list(dict.fromkeys(ids))
            if not ids:
                # Empty means "unrestricted at this level" — still resolve to
                # an empty instance list so update() clears any previously
                # granted records at this level instead of leaving them stale.
                resolved_locations[accessor] = []
                continue

            qs = model.objects.filter(unique_id__in=ids, is_deleted=False)
            if project_scoped:
                qs = qs.filter(company_id_id=company.unique_id)
                if found_project_ids:
                    qs = qs.filter(project_id_id__in=found_project_ids)
            instances = list(qs)
            found_ids = {obj.unique_id for obj in instances}
            missing_ids = [i for i in ids if i not in found_ids]
            if missing_ids:
                raise serializers.ValidationError({
                    field_key: f"Invalid {field_key}: {', '.join(missing_ids)}"
                })
            resolved_locations[accessor] = instances

        permissions = data.get("permissions") or []
        enabled_keys = _project_enabled_screen_action_keys(company.unique_id, found_project_ids)

        normalized_permissions = []
        invalid = []
        for perm in permissions:
            userscreen_id = perm["userscreen_id"]
            for action_id in perm["action_ids"]:
                key = (userscreen_id, action_id)
                if key not in enabled_keys:
                    invalid.append(f"{userscreen_id}:{action_id}")
                    continue
                normalized_permissions.append({
                    "mainscreen_id": enabled_keys[key],
                    "userscreen_id": userscreen_id,
                    "userscreenaction_id": action_id,
                })

        if invalid:
            raise serializers.ValidationError({
                "permissions": (
                    "The following screen/action grants are not enabled for these projects "
                    f"by Super Admin: {', '.join(sorted(invalid))}"
                )
            })

        data["resolved_staff"] = staff
        data["resolved_company"] = company
        data["resolved_projects"] = projects
        data["resolved_locations"] = resolved_locations
        data["resolved_permissions"] = normalized_permissions
        return data

    @transaction.atomic
    def create(self, validated_data):
        primary_project = validated_data["resolved_projects"][0] if validated_data["resolved_projects"] else None
        staff = validated_data["resolved_staff"] or self._save_staff(
            validated_data["resolved_company"],
            primary_project,
        )
        instance, _ = StaffAccessConfiguration.objects.update_or_create(
            staff_id=staff,
            defaults={
                "company_id": validated_data["resolved_company"],
                "description": validated_data.get("description", ""),
                "is_deleted": False,
                "is_active": True,
            },
        )
        instance.projects.set(validated_data["resolved_projects"])
        for accessor, instances in validated_data["resolved_locations"].items():
            getattr(instance, accessor).set(instances)
        self._sync_permissions(instance, validated_data["resolved_permissions"])
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        primary_project = validated_data["resolved_projects"][0] if validated_data["resolved_projects"] else None
        staff = self._save_staff(
            validated_data["resolved_company"],
            primary_project,
            validated_data["resolved_staff"] or instance.staff_id,
        )
        instance.staff_id = staff
        instance.company_id = validated_data["resolved_company"]
        instance.description = validated_data.get("description", instance.description)
        instance.save()

        instance.projects.set(validated_data["resolved_projects"])
        for accessor, instances in validated_data["resolved_locations"].items():
            getattr(instance, accessor).set(instances)

        if "permissions" in self.initial_data:
            self._sync_permissions(instance, validated_data["resolved_permissions"])
        return instance

    def _sync_permissions(self, instance, permissions):
        existing = {
            (p.userscreen_id_id, p.userscreenaction_id_id): p
            for p in instance.granted_permissions.filter(is_deleted=False)
        }
        incoming_keys = set()
        for order_no, perm in enumerate(permissions, start=1):
            key = (perm["userscreen_id"], perm["userscreenaction_id"])
            incoming_keys.add(key)
            if key in existing:
                continue
            StaffAccessConfigurationPermission.objects.create(
                staff_access_configuration_id=instance,
                mainscreen_id_id=perm["mainscreen_id"],
                userscreen_id_id=perm["userscreen_id"],
                userscreenaction_id_id=perm["userscreenaction_id"],
                order_no=order_no,
            )

        for key, obj in existing.items():
            if key not in incoming_keys:
                obj.is_deleted = True
                obj.is_active = False
                obj.save(update_fields=["is_deleted", "is_active"])
