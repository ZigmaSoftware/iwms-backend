from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from app.models.superadmin.common_masters.state import State
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.superadmin.screen_management.companyuserscreenpermission import (
    CompanyUserScreenPermission,
)
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.superadmin.screen_management.app_module import AppModule
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfiguration,
    StaffAccessConfigurationPermission,
)
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
from app.serializers.superadmin.staff_management.staffcreation_serializer import StaffcreationSerializer


# (write-payload key, model, field name storing the comma-separated ids on
# StaffAccessConfiguration, is geo-scoped-to-project)
LOCATION_LEVELS = (
    ("state_ids", State, "state_ids", False),
    ("district_ids", District, "district_ids", True),
    ("city_ids", City, "city_ids", True),
    ("zone_ids", Zone, "zone_ids", True),
    ("panchayat_ids", Panchayat, "panchayat_ids", True),
    ("ward_ids", Ward, "ward_ids", True),
)


def _project_enabled_screen_action_keys(company_id, project_ids):
    """(userscreen_id, userscreenaction_id) pairs enabled for the given
    projects' catalogs. `project_ids` falsy/empty means "no project
    restriction" — i.e. the staff is scoped to the whole company, so the
    catalog is the company-level (project_id IS NULL) permissions only."""
    qs = CompanyUserScreenPermission.objects.filter(
        company_id=company_id,
        permission_type="screen",
        is_deleted=False,
        is_active=True,
    )
    if project_ids:
        qs = qs.filter(project_id__in=project_ids)
    else:
        qs = qs.filter(project_id__isnull=True)
    qs = qs.exclude(
        Q(userscreenaction_id__in=_action_ids_named("show"))
    ).values_list("userscreen_id", "userscreenaction_id", "mainscreen_id")
    return {(row[0], row[1]): row[2] for row in qs}


def _action_ids_named(name):
    from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
    return UserScreenAction.objects.filter(
        Q(action_name__iexact=name) | Q(variable_name__iexact=name)
    ).values_list("unique_id", flat=True)


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

    staff_name = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    employee_name = serializers.SerializerMethodField()
    contact_mobile = serializers.SerializerMethodField()
    contact_email = serializers.SerializerMethodField()
    doj = serializers.SerializerMethodField()
    user_type_id = serializers.SerializerMethodField()
    staffusertype_id = serializers.SerializerMethodField()
    staffusertype_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()

    # The one app this staff member signs into. Selecting a module is what
    # makes the mobile login succeed at all; what they can do inside comes
    # from the screen permissions below, which are the same rows that govern
    # web. `app_module_ids` is still accepted (and must hold at most one id)
    # so an older web build's payload does not start failing mid-rollout.
    app_module_id = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, write_only=True
    )
    app_module_ids = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )

    granted_permissions = serializers.SerializerMethodField()
    main_screen_count = serializers.SerializerMethodField()
    screen_count = serializers.SerializerMethodField()

    class Meta:
        model = StaffAccessConfiguration
        exclude = ()

    # -- helpers to resolve the staff behind `staff_id` (a plain CharField
    # holding StaffcreationOfficeDetails.staff_unique_id) for the read-only
    # profile fields below. Resolved once per representation via `_staff`,
    # not per-field, to avoid N queries per row in list views.
    def _staff_for(self, obj):
        cache = getattr(self, "_staff_cache", None)
        if cache is None:
            cache = {}
            self._staff_cache = cache
        if obj.unique_id not in cache:
            cache[obj.unique_id] = obj.staff
        return cache[obj.unique_id]

    def get_staff_name(self, obj):
        staff = self._staff_for(obj)
        return staff.employee_name if staff else None

    def get_username(self, obj):
        staff = self._staff_for(obj)
        return staff.username if staff else None

    def get_employee_name(self, obj):
        staff = self._staff_for(obj)
        return staff.employee_name if staff else None

    def get_contact_mobile(self, obj):
        staff = self._staff_for(obj)
        personal = getattr(staff, "personal_details", None) if staff else None
        return getattr(personal, "contact_mobile", None)

    def get_contact_email(self, obj):
        staff = self._staff_for(obj)
        personal = getattr(staff, "personal_details", None) if staff else None
        return getattr(personal, "contact_email", None)

    def get_doj(self, obj):
        staff = self._staff_for(obj)
        return staff.doj if staff else None

    def get_user_type_id(self, obj):
        staff = self._staff_for(obj)
        return staff.user_type_id if staff else None

    def get_staffusertype_id(self, obj):
        staff = self._staff_for(obj)
        return staff.staffusertype_id if staff else None

    def get_staffusertype_name(self, obj):
        staff = self._staff_for(obj)
        usertype = getattr(staff, "staffusertype", None) if staff else None
        return getattr(usertype, "name", None)

    def get_company_name(self, obj):
        company = obj.company
        return company.name if company else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["staff_id"] = instance.staff_id
        data["staff_unique_id"] = instance.staff_id
        data["company_id"] = instance.company_id

        module = instance.app_module if instance.app_module_id else None
        if module and module.is_deleted:
            module = None
        data["app_module_id"] = module.unique_id if module else None
        data["app_module_key"] = module.surface_key if module else None
        data["app_module_label"] = module.label if module else None

        project_ids = instance.get_project_ids()
        projects = list(Project.objects.filter(unique_id__in=project_ids)) if project_ids else []
        projects_by_id = {p.unique_id: p for p in projects}
        data["project_ids"] = project_ids
        data["project_names"] = [
            projects_by_id[pid].name for pid in project_ids if pid in projects_by_id
        ]

        name_fields = {
            "state_ids": (State, "name"),
            "district_ids": (District, "name"),
            "city_ids": (City, "name"),
            "zone_ids": (Zone, "zone_name"),
            "panchayat_ids": (Panchayat, "panchayat_name"),
            "ward_ids": (Ward, "ward_name"),
        }
        resolved_states = []
        for field_key, (model, name_field) in name_fields.items():
            ids = getattr(instance, f"get_{field_key}")()
            rows = list(model.objects.filter(unique_id__in=ids)) if ids else []
            rows_by_id = {r.unique_id: r for r in rows}
            singular = field_key[:-4] if field_key != "city_ids" else "city"
            data[f"{singular}_ids"] = ids
            data[f"{singular}_names"] = [
                getattr(rows_by_id[i], name_field) for i in ids if i in rows_by_id
            ]
            if field_key == "state_ids":
                resolved_states = rows

        continent_ids = []
        continent_names = []
        country_ids = []
        country_names = []
        for state in resolved_states:
            continent = state.continent
            if continent and continent.unique_id not in continent_ids:
                continent_ids.append(continent.unique_id)
                continent_names.append(continent.name)
            country = state.country
            if country and country.unique_id not in country_ids:
                country_ids.append(country.unique_id)
                country_names.append(country.name)
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
            staff = instance.staff
            if staff:
                staff_data = StaffcreationSerializer(staff, context=self.context).data
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

    def _save_staff(self, company, project_id, existing_staff=None):
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
        return serializer.save(company_id=company.unique_id, project_id=project_id)

    def get_granted_permissions(self, obj):
        rows = StaffAccessConfigurationPermission.objects.filter(
            staff_access_configuration_id=obj.unique_id, is_deleted=False,
        )
        rows = list(rows)

        from app.models.superadmin.screen_management.mainscreen import MainScreen
        from app.models.superadmin.screen_management.userscreen import UserScreen

        mainscreen_ids = {r.mainscreen_id for r in rows if r.mainscreen_id}
        userscreen_ids = {r.userscreen_id for r in rows if r.userscreen_id}
        mainscreens = {
            m.unique_id: m for m in MainScreen.objects.filter(unique_id__in=mainscreen_ids)
        }
        userscreens = {
            u.unique_id: u for u in UserScreen.objects.filter(unique_id__in=userscreen_ids)
        }

        grouped = {}
        for row in rows:
            mainscreen = mainscreens.get(row.mainscreen_id)
            userscreen = userscreens.get(row.userscreen_id)
            screen = grouped.setdefault(
                row.userscreen_id,
                {
                    "mainScreenId": row.mainscreen_id,
                    "mainScreenName": mainscreen.mainscreen_name if mainscreen else None,
                    "userScreenId": row.userscreen_id,
                    "userScreenName": userscreen.userscreen_name if userscreen else None,
                    "actionIds": [],
                },
            )
            screen["actionIds"].append(row.userscreenaction_id)
        return list(grouped.values())

    def get_main_screen_count(self, obj):
        return (
            StaffAccessConfigurationPermission.objects.filter(
                staff_access_configuration_id=obj.unique_id, is_deleted=False,
            )
            .values("mainscreen_id")
            .distinct()
            .count()
        )

    def get_screen_count(self, obj):
        return (
            StaffAccessConfigurationPermission.objects.filter(
                staff_access_configuration_id=obj.unique_id, is_deleted=False,
            )
            .values("userscreen_id")
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
            unique_id__in=project_ids, company_id=company.unique_id, is_deleted=False,
        ))
        found_project_ids = {p.unique_id for p in projects}
        missing = [pid for pid in project_ids if pid not in found_project_ids]
        if missing:
            raise serializers.ValidationError({
                "project_ids": f"Invalid project(s) for company: {', '.join(missing)}"
            })

        resolved_locations = {}
        for field_key, model, storage_field, project_scoped in LOCATION_LEVELS:
            ids = data.get(field_key) or self._nested_list(
                "dataScope", field_key, field_key[:-4] + "Ids"
            )
            ids = list(dict.fromkeys(ids))
            if not ids:
                # Empty means "unrestricted at this level" — still resolve to
                # an empty id list so update() clears any previously granted
                # ids at this level instead of leaving them stale.
                resolved_locations[storage_field] = []
                continue

            qs = model.objects.filter(unique_id__in=ids, is_deleted=False)
            if project_scoped:
                qs = qs.filter(company_id=company.unique_id)
                if found_project_ids:
                    qs = qs.filter(project_id__in=found_project_ids)
            instances = list(qs)
            found_ids = {obj.unique_id for obj in instances}
            missing_ids = [i for i in ids if i not in found_ids]
            if missing_ids:
                raise serializers.ValidationError({
                    field_key: f"Invalid {field_key}: {', '.join(missing_ids)}"
                })
            resolved_locations[storage_field] = [obj.unique_id for obj in instances]

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

        data["resolved_app_module"] = self._resolve_app_module(data)

        data["resolved_staff"] = staff
        data["resolved_company"] = company
        data["resolved_project_ids"] = list(found_project_ids)
        data["resolved_locations"] = resolved_locations
        data["resolved_permissions"] = normalized_permissions
        return data

    def _app_module_field_sent(self):
        """Whether the caller addressed the app at all in this payload.

        Both the current `app_module_id` and the older `app_module_ids` list
        count, so a web build mid-rollout keeps working. Omitting both leaves
        the existing selection alone, so a partial update cannot silently
        revoke someone's app access.
        """
        source = self.initial_data if isinstance(self.initial_data, dict) else {}
        return "app_module_id" in source or "app_module_ids" in source

    def _resolve_app_module(self, data):
        """The single AppModule this configuration grants, or None.

        A person belongs to one app, so `app_module_ids` (the legacy list) is
        rejected outright when it carries more than one id rather than
        silently keeping the first — an admin who ticked two apps needs to be
        told which one actually took effect.
        """
        source = self.initial_data if isinstance(self.initial_data, dict) else {}

        module_id = data.get("app_module_id")
        if module_id is None:
            module_id = source.get("app_module_id")

        if not module_id:
            legacy_ids = data.get("app_module_ids")
            if legacy_ids is None:
                legacy_ids = source.get("app_module_ids")
            legacy_ids = list(dict.fromkeys(legacy_ids or []))
            if len(legacy_ids) > 1:
                raise serializers.ValidationError({
                    "app_module_id": (
                        "A staff member can belong to only one mobile app. "
                        f"Received {len(legacy_ids)}: {', '.join(legacy_ids)}"
                    )
                })
            module_id = legacy_ids[0] if legacy_ids else None

        module_id = (module_id or "").strip()
        if not module_id:
            return None

        module = AppModule.objects.filter(
            unique_id=module_id, is_active=True, is_deleted=False,
        ).first()
        if not module:
            raise serializers.ValidationError({
                "app_module_id": f"Invalid app module: {module_id}"
            })
        return module

    @transaction.atomic
    def create(self, validated_data):
        resolved_project_ids = validated_data["resolved_project_ids"]
        primary_project_id = resolved_project_ids[0] if resolved_project_ids else None
        staff = validated_data["resolved_staff"] or self._save_staff(
            validated_data["resolved_company"],
            primary_project_id,
        )
        instance, _ = StaffAccessConfiguration.objects.update_or_create(
            staff_id=staff.staff_unique_id,
            defaults={
                "company_id": validated_data["resolved_company"].unique_id,
                "description": validated_data.get("description", ""),
                "is_deleted": False,
                "is_active": True,
            },
        )
        instance.project_ids = ",".join(resolved_project_ids)
        for storage_field, ids in validated_data["resolved_locations"].items():
            setattr(instance, storage_field, ",".join(ids))
        instance.save()
        self._sync_app_module(instance, validated_data)
        self._sync_permissions(instance, validated_data["resolved_permissions"])
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        resolved_project_ids = validated_data["resolved_project_ids"]
        primary_project_id = resolved_project_ids[0] if resolved_project_ids else None
        staff = self._save_staff(
            validated_data["resolved_company"],
            primary_project_id,
            validated_data["resolved_staff"] or instance.staff,
        )
        instance.staff_id = staff.staff_unique_id
        instance.company_id = validated_data["resolved_company"].unique_id
        instance.description = validated_data.get("description", instance.description)

        instance.project_ids = ",".join(resolved_project_ids)
        for storage_field, ids in validated_data["resolved_locations"].items():
            setattr(instance, storage_field, ",".join(ids))
        instance.save()

        self._sync_app_module(instance, validated_data)

        if "permissions" in self.initial_data:
            self._sync_permissions(instance, validated_data["resolved_permissions"])
        return instance

    def _sync_app_module(self, instance, validated_data):
        """Set the selected app, when the caller addressed it in this payload."""
        if not self._app_module_field_sent():
            return
        module = validated_data.get("resolved_app_module")
        new_app_module_id = module.unique_id if module else None
        if instance.app_module_id != new_app_module_id:
            instance.app_module_id = new_app_module_id
            instance.save(update_fields=["app_module_id"])

    def _sync_permissions(self, instance, permissions):
        existing = {
            (p.userscreen_id, p.userscreenaction_id): p
            for p in StaffAccessConfigurationPermission.objects.filter(
                staff_access_configuration_id=instance.unique_id, is_deleted=False,
            )
        }
        incoming_keys = set()
        for order_no, perm in enumerate(permissions, start=1):
            key = (perm["userscreen_id"], perm["userscreenaction_id"])
            incoming_keys.add(key)
            if key in existing:
                continue
            StaffAccessConfigurationPermission.objects.create(
                staff_access_configuration_id=instance.unique_id,
                mainscreen_id=perm["mainscreen_id"],
                userscreen_id=perm["userscreen_id"],
                userscreenaction_id=perm["userscreenaction_id"],
                order_no=order_no,
            )

        for key, obj in existing.items():
            if key not in incoming_keys:
                obj.is_deleted = True
                obj.is_active = False
                obj.save(update_fields=["is_deleted", "is_active"])
