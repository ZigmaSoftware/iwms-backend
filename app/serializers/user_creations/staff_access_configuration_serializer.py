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
from app.serializers.user_creations.staffcreation_serializer import StaffcreationSerializer


LOCATION_FIELDS = (
    "state_id",
    "district_id",
    "city_id",
    "zone_id",
    "panchayat_id",
    "ward_id",
)

LOCATION_MODELS = {
    "state_id": State,
    "district_id": District,
    "city_id": City,
    "zone_id": Zone,
    "panchayat_id": Panchayat,
    "ward_id": Ward,
}


def _project_enabled_screen_action_keys(company_id, project_id):
    """(userscreen_id, userscreenaction_id) pairs enabled for a project's catalog."""
    qs = CompanyUserScreenPermission.objects.filter(
        company_id_id=company_id,
        project_id_id=project_id,
        permission_type="screen",
        is_deleted=False,
        is_active=True,
    ).exclude(
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
    project_id = serializers.CharField()

    state_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    district_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    city_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    zone_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    panchayat_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    ward_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

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
    project_name = serializers.CharField(source="project_id.name", read_only=True)
    state_name = serializers.CharField(source="state_id.name", read_only=True, default=None)
    district_name = serializers.CharField(source="district_id.name", read_only=True, default=None)
    city_name = serializers.CharField(source="city_id.name", read_only=True, default=None)
    zone_name = serializers.CharField(source="zone_id.zone_name", read_only=True, default=None)
    panchayat_name = serializers.CharField(source="panchayat_id.panchayat_name", read_only=True, default=None)
    ward_name = serializers.CharField(source="ward_id.ward_name", read_only=True, default=None)

    granted_permissions = serializers.SerializerMethodField()
    main_screen_count = serializers.SerializerMethodField()
    screen_count = serializers.SerializerMethodField()

    class Meta:
        model = StaffAccessConfiguration
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["staff_id"] = instance.staff_id_id
        data["staff_unique_id"] = instance.staff_id_id
        data["company_id"] = instance.company_id_id
        data["project_id"] = instance.project_id_id
        for field in LOCATION_FIELDS:
            data[field] = getattr(instance, f"{field}_id")
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

    def _nested_id(self, group, snake_key, camel_key=None):
        source = self.initial_data or {}
        nested = source.get(group) if isinstance(source, dict) else None
        if isinstance(nested, dict):
            value = nested.get(camel_key or snake_key) or nested.get(snake_key)
            if value not in ("", None):
                return str(value).strip()
        value = source.get(snake_key) if isinstance(source, dict) else None
        if value not in ("", None):
            return str(value).strip()
        return None

    def _build_staff_payload(self, staff=None):
        source = self.initial_data or {}
        basic = source.get("basicInfo") if isinstance(source, dict) else {}
        login = source.get("loginConfig") if isinstance(source, dict) else {}
        basic = basic if isinstance(basic, dict) else {}
        login = login if isinstance(login, dict) else {}

        payload = {
            "company_id": self._nested_value("company_id", "companyId"),
            "project_id": self._nested_value("project_id", "projectId"),
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
        project_id = data.get("project_id")

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

        try:
            project = Project.objects.get(unique_id=project_id, company_id_id=company.unique_id, is_deleted=False)
        except Project.DoesNotExist:
            raise serializers.ValidationError({"project_id": "Invalid project for company"})

        resolved_locations = {}
        for field in LOCATION_FIELDS:
            value = (
                data.get(field)
                or self._nested_id("dataScope", field, field.replace("_id", "Id"))
                or ""
            ).strip()
            value = value or None
            resolved_locations[field] = None
            if value:
                model = LOCATION_MODELS[field]
                try:
                    resolved_locations[field] = model.objects.get(unique_id=value, is_deleted=False)
                except model.DoesNotExist:
                    raise serializers.ValidationError({field: f"Invalid {field}"})

        permissions = data.get("permissions") or []
        enabled_keys = _project_enabled_screen_action_keys(company.unique_id, project.unique_id)

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
                    "The following screen/action grants are not enabled for this project "
                    f"by Super Admin: {', '.join(sorted(invalid))}"
                )
            })

        data["resolved_staff"] = staff
        data["resolved_company"] = company
        data["resolved_project"] = project
        data["resolved_locations"] = resolved_locations
        data["resolved_permissions"] = normalized_permissions
        return data

    @transaction.atomic
    def create(self, validated_data):
        staff = validated_data["resolved_staff"] or self._save_staff(
            validated_data["resolved_company"],
            validated_data["resolved_project"],
        )
        instance, _ = StaffAccessConfiguration.objects.update_or_create(
            staff_id=staff,
            defaults={
                "company_id": validated_data["resolved_company"],
                "project_id": validated_data["resolved_project"],
                "description": validated_data.get("description", ""),
                **validated_data["resolved_locations"],
                "is_deleted": False,
                "is_active": True,
            },
        )
        self._sync_permissions(instance, validated_data["resolved_permissions"])
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        staff = self._save_staff(
            validated_data["resolved_company"],
            validated_data["resolved_project"],
            validated_data["resolved_staff"] or instance.staff_id,
        )
        instance.staff_id = staff
        instance.company_id = validated_data["resolved_company"]
        instance.project_id = validated_data["resolved_project"]
        instance.description = validated_data.get("description", instance.description)
        for field, value in validated_data["resolved_locations"].items():
            setattr(instance, field, value)
        instance.save()

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
