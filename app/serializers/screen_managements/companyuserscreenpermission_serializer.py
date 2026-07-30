from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from app.models.screen_managements.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)
from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission, PermissionType
from app.models.screen_managements.mainscreen import MainScreen
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.userscreenaction import UserScreenAction
from app.models.screen_managements.userscreencolumn import UserScreenColumn
from app.models.superadmin_masters.project import Project
from app.models.superadmin_masters.company import Company

from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward


SUPPORTED_ACTION_NAMES = {"add", "edit", "delete", "view"}


class CompanyUserScreenPermissionSerializer(serializers.ModelSerializer):
    userscreen_name = serializers.CharField(source="userscreen_id.userscreen_name", read_only=True)
    userscreenaction_name = serializers.CharField(source="userscreenaction_id.action_name", read_only=True)
    mainscreen_name = serializers.CharField(source="mainscreen_id.mainscreen_name", read_only=True)
    company_name = serializers.CharField(source="company_id.name", read_only=True)
    project_name = serializers.CharField(source="project_id.name", read_only=True, allow_null=True, default=None)
    state_name = serializers.CharField(source="state_id.name", read_only=True, allow_null=True, default=None)
    district_name = serializers.CharField(source="district_id.name", read_only=True, allow_null=True, default=None)
    city_name = serializers.CharField(source="city_id.name", read_only=True, allow_null=True, default=None)
    zone_name = serializers.CharField(source="zone_id.zone_name", read_only=True, allow_null=True, default=None)
    panchayat_name = serializers.CharField(
        source="panchayat_id.panchayat_name", read_only=True, allow_null=True, default=None
    )
    ward_name = serializers.CharField(source="ward_id.ward_name", read_only=True, allow_null=True, default=None)

    class Meta:
        model = CompanyUserScreenPermission
        fields = "__all__"


class ScreenActionSerializer(serializers.Serializer):
    userscreen_id = serializers.CharField(required=False)
    userScreenId = serializers.CharField(required=False)
    actions = serializers.ListField(child=serializers.JSONField(), allow_empty=True, required=False)
    actionIds = serializers.ListField(child=serializers.CharField(), allow_empty=True, required=False)
    columnIds = serializers.ListField(child=serializers.CharField(), allow_empty=True, required=False)
    columns = serializers.ListField(child=serializers.DictField(), allow_empty=True, required=False)
    meta = serializers.DictField(required=False)

    def validate(self, data):
        data["userscreen_id"] = data.get("userscreen_id") or data.get("userScreenId")
        screen_is_active = (data.get("meta") or {}).get("isActive", True)

        action_ids = data.get("actionIds")
        if action_ids is None:
            action_ids = []
            for action in data.get("actions", []):
                if isinstance(action, dict):
                    if action.get("isActive", action.get("is_active", True)):
                        action_id = action.get("actionId") or action.get("action_id") or action.get("id")
                        if action_id:
                            action_ids.append(action_id)
                elif action:
                    action_ids.append(action)
        data["actionIds"] = action_ids

        column_permissions = None
        if "columns" in data:
            column_permissions = []
            for column in data.get("columns", []):
                column_id = column.get("columnId") or column.get("column_id") or column.get("id")
                if not column_id:
                    raise serializers.ValidationError({"columns": "columnId is required."})
                column_permissions.append({
                    "column_id": column_id,
                    "field_name": column.get("fieldName") or column.get("field_name"),
                    "can_view": column.get("canView", column.get("can_view", True)),
                    "order_no": column.get("orderNo") or column.get("order_no"),
                    "is_required": column.get("isRequired", column.get("is_required")),
                })
            data["columnIds"] = [item["column_id"] for item in column_permissions]
        else:
            data["columnIds"] = data.get("columnIds", None)

        data["columnPermissions"] = column_permissions
        if not screen_is_active:
            data["actionIds"] = []
            if column_permissions is not None:
                data["columnPermissions"] = []
                data["columnIds"] = []
        if not data["userscreen_id"]:
            raise serializers.ValidationError({"userscreen_id": "This field is required."})
        return data


class CompanyUserScreenPermissionMultiScreenSerializer(serializers.Serializer):
    company_id = serializers.CharField(required=False)
    companyId = serializers.CharField(required=False)
    project_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    projectId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    mainscreen_id = serializers.CharField(required=False)
    mainScreenId = serializers.CharField(required=False)
    permission_type = serializers.ChoiceField(
        choices=PermissionType.choices, required=False, allow_blank=True, allow_null=True
    )
    permissionType = serializers.ChoiceField(
        choices=PermissionType.choices, required=False, allow_blank=True, allow_null=True
    )
    screens = ScreenActionSerializer(many=True, required=False)
    userScreens = ScreenActionSerializer(many=True, required=False)
    description = serializers.CharField(required=False, allow_blank=True)

    state_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    stateId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    district_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    districtId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    city_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cityId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    zone_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    zoneId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    panchayat_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    panchayatId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    ward_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    wardId = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, data):
        data["company_id"] = (data.get("company_id") or data.get("companyId") or "").strip()
        data["project_id"] = (data.get("project_id") or data.get("projectId") or "").strip() or None
        data["state_id"] = (data.get("state_id") or data.get("stateId") or "").strip() or None
        data["district_id"] = (data.get("district_id") or data.get("districtId") or "").strip() or None
        data["city_id"] = (data.get("city_id") or data.get("cityId") or "").strip() or None
        data["zone_id"] = (data.get("zone_id") or data.get("zoneId") or "").strip() or None
        data["panchayat_id"] = (data.get("panchayat_id") or data.get("panchayatId") or "").strip() or None
        data["ward_id"] = (data.get("ward_id") or data.get("wardId") or "").strip() or None
        data["mainscreen_id"] = (data.get("mainscreen_id") or data.get("mainScreenId") or "").strip()
        data["permission_type"] = (
            data.get("permission_type") or data.get("permissionType") or PermissionType.SCREEN
        )
        data["screens"] = data.get("screens") or data.get("userScreens") or []

        if not data["company_id"]:
            raise serializers.ValidationError({"company_id": "This field is required."})
        if not data["mainscreen_id"]:
            raise serializers.ValidationError({"mainscreen_id": "This field is required."})
        if not data["screens"]:
            raise serializers.ValidationError({"screens": "At least one screen required."})

        try:
            company = Company.objects.get(unique_id=data["company_id"], is_deleted=False)
        except Company.DoesNotExist:
            raise serializers.ValidationError({"company_id": "Invalid company"})

        project = None
        if data["project_id"]:
            try:
                project = Project.objects.get(
                    unique_id=data["project_id"],
                    company_id_id=company.unique_id,
                    is_deleted=False,
                )
            except Project.DoesNotExist:
                raise serializers.ValidationError({"project_id": "Invalid project for company"})

        state = None
        if data["state_id"]:
            try:
                state = State.objects.get(unique_id=data["state_id"], is_deleted=False)
            except State.DoesNotExist:
                raise serializers.ValidationError({"state_id": "Invalid state"})

        district = None
        if data["district_id"]:
            try:
                district = District.objects.get(unique_id=data["district_id"], is_deleted=False)
            except District.DoesNotExist:
                raise serializers.ValidationError({"district_id": "Invalid district"})

        city = None
        if data["city_id"]:
            try:
                city = City.objects.get(unique_id=data["city_id"], is_deleted=False)
            except City.DoesNotExist:
                raise serializers.ValidationError({"city_id": "Invalid city"})

        zone = None
        if data["zone_id"]:
            try:
                zone = Zone.objects.get(unique_id=data["zone_id"], is_deleted=False)
            except Zone.DoesNotExist:
                raise serializers.ValidationError({"zone_id": "Invalid zone"})

        panchayat = None
        if data["panchayat_id"]:
            try:
                panchayat = Panchayat.objects.get(unique_id=data["panchayat_id"], is_deleted=False)
            except Panchayat.DoesNotExist:
                raise serializers.ValidationError({"panchayat_id": "Invalid panchayat"})

        ward = None
        if data["ward_id"]:
            try:
                ward = Ward.objects.get(unique_id=data["ward_id"], is_deleted=False)
            except Ward.DoesNotExist:
                raise serializers.ValidationError({"ward_id": "Invalid ward"})

        try:
            mainscreen = MainScreen.objects.get(unique_id=data["mainscreen_id"], is_deleted=False)
        except MainScreen.DoesNotExist:
            raise serializers.ValidationError({"mainscreen_id": "Invalid mainscreen"})

        screen_ids = {screen["userscreen_id"] for screen in data["screens"]}
        valid_screen_ids = set(
            UserScreen.objects.filter(
                unique_id__in=screen_ids,
                mainscreen_id_id=mainscreen.unique_id,
                is_deleted=False,
            ).values_list("unique_id", flat=True)
        )
        invalid_screens = screen_ids - valid_screen_ids
        if invalid_screens:
            raise serializers.ValidationError({
                "screens": f"Invalid userscreens for mainscreen: {', '.join(sorted(invalid_screens))}"
            })

        action_values = {
            str(action_id).strip()
            for screen in data["screens"]
            for action_id in screen.get("actionIds", [])
            if str(action_id).strip()
        }
        if action_values:
            for action_value in action_values:
                normalized = action_value.lower()
                if normalized in SUPPORTED_ACTION_NAMES:
                    UserScreenAction.objects.get_or_create(
                        action_name=normalized,
                        defaults={
                            "variable_name": normalized,
                            "is_active": True,
                            "is_deleted": False,
                        },
                    )

            actions = UserScreenAction.objects.filter(is_deleted=False)
            action_lookup = {}
            for action in actions:
                action_lookup[str(action.unique_id).lower()] = action.unique_id
                action_lookup[(action.action_name or "").lower()] = action.unique_id
                action_lookup[(action.variable_name or "").lower()] = action.unique_id

            invalid_actions = []
            for screen in data["screens"]:
                normalized_action_ids = []
                for action_value in screen.get("actionIds", []):
                    resolved_action_id = action_lookup.get(str(action_value).strip().lower())
                    if resolved_action_id:
                        normalized_action_ids.append(resolved_action_id)
                    else:
                        invalid_actions.append(str(action_value))
                screen["actionIds"] = normalized_action_ids

            if invalid_actions:
                raise serializers.ValidationError({
                    "screens": f"Invalid actions: {', '.join(sorted(invalid_actions))}"
                })

        for screen in data["screens"]:
            column_ids = screen.get("columnIds")
            if column_ids is None:
                continue
            screen_columns = UserScreenColumn.objects.filter(
                userscreen_id_id=screen["userscreen_id"],
                is_active=True,
                is_deleted=False,
            )
            column_lookup = {}
            for column in screen_columns:
                column_lookup[str(column.unique_id).lower()] = column
                column_lookup[(column.field_name or "").lower()] = column

            normalized_column_ids = []
            invalid_columns = []

            if screen.get("columnPermissions") is not None:
                for column_permission in screen["columnPermissions"]:
                    lookup_values = [
                        column_permission.get("column_id"),
                        column_permission.get("field_name"),
                    ]
                    column = None
                    for lookup_value in lookup_values:
                        if lookup_value:
                            column = column_lookup.get(str(lookup_value).strip().lower())
                            if column:
                                break
                    if not column:
                        invalid_columns.append(str(column_permission.get("column_id")))
                        continue
                    field_name = column_permission.get("field_name")
                    if field_name and field_name != column.field_name:
                        raise serializers.ValidationError({
                            "columns": (
                                f"fieldName '{field_name}' does not match "
                                f"columnId '{column.unique_id}'."
                            )
                        })
                    column_permission["column_id"] = column.unique_id
                    column_permission["field_name"] = column.field_name
                    normalized_column_ids.append(column.unique_id)
            else:
                for column_id in column_ids:
                    column = column_lookup.get(str(column_id).strip().lower())
                    if column:
                        normalized_column_ids.append(column.unique_id)
                    else:
                        invalid_columns.append(str(column_id))

            if invalid_columns:
                raise serializers.ValidationError({
                    "columnIds": (
                        "Columns do not belong to the selected userscreen: "
                        f"{', '.join(sorted(invalid_columns))}"
                    )
                })
            screen["columnIds"] = normalized_column_ids

        data["resolved_company_id"] = company.unique_id
        data["resolved_project_id"] = project.unique_id if project else None
        data["resolved_state_id"] = state.unique_id if state else None
        data["resolved_district_id"] = district.unique_id if district else None
        data["resolved_city_id"] = city.unique_id if city else None
        data["resolved_zone_id"] = zone.unique_id if zone else None
        data["resolved_panchayat_id"] = panchayat.unique_id if panchayat else None
        data["resolved_ward_id"] = ward.unique_id if ward else None
        data["resolved_mainscreen_id"] = mainscreen.unique_id
        return data

    @transaction.atomic
    def create(self, validated_data):
        company_id = validated_data["resolved_company_id"]
        project_id = validated_data["resolved_project_id"]
        state_id = validated_data.get("resolved_state_id")
        district_id = validated_data.get("resolved_district_id")
        city_id = validated_data.get("resolved_city_id")
        zone_id = validated_data.get("resolved_zone_id")
        panchayat_id = validated_data.get("resolved_panchayat_id")
        ward_id = validated_data.get("resolved_ward_id")
        permission_type = validated_data.get("permission_type") or PermissionType.SCREEN
        mainscreen_id = validated_data["resolved_mainscreen_id"]
        screens = validated_data["screens"]
        desc = (validated_data.get("description") or "").strip()
        update_only = bool(self.context.get("update_only", False))

        created, updated, deleted = [], [], []
        created_columns, updated_columns, deleted_columns = [], [], []

        existing_qs = CompanyUserScreenPermission.objects.select_related(
            "userscreen_id", "userscreenaction_id"
        ).filter(
            company_id_id=company_id,
            project_id_id=project_id,
            mainscreen_id_id=mainscreen_id,
            permission_type=permission_type,
        )
        existing_lookup = {
            (obj.userscreen_id_id, obj.userscreenaction_id_id): obj
            for obj in existing_qs
        }
        incoming_action_keys = set()

        for screen in screens:
            screen_id = screen["userscreen_id"]
            screen_meta = screen.get("meta") or {}
            screen_desc = screen_meta.get("description", desc)
            for order_no, action_id in enumerate(screen.get("actionIds", []), start=1):
                key = (screen_id, action_id)
                incoming_action_keys.add(key)
                permission = existing_lookup.get(key)
                if permission:
                    permission.is_deleted = False
                    permission.is_active = True
                    permission.order_no = order_no
                    permission.description = screen_desc
                    permission.permission_type = permission_type
                    permission.project_id_id = project_id
                    permission.state_id_id = state_id
                    permission.district_id_id = district_id
                    permission.city_id_id = city_id
                    permission.zone_id_id = zone_id
                    permission.panchayat_id_id = panchayat_id
                    permission.ward_id_id = ward_id
                    permission.save(update_fields=[
                        "is_deleted",
                        "is_active",
                        "order_no",
                        "description",
                        "permission_type",
                        "project_id",
                        "state_id",
                        "district_id",
                        "city_id",
                        "zone_id",
                        "panchayat_id",
                        "ward_id",
                        "updated_at",
                    ])
                    updated.append(permission)
                    continue

                if update_only:
                    raise serializers.ValidationError({
                        "screens": f"Update mode cannot create {screen_id}:{action_id}"
                    })

                permission = CompanyUserScreenPermission.objects.create(
                    company_id_id=company_id,
                    project_id_id=project_id,
                    state_id_id=state_id,
                    district_id_id=district_id,
                    city_id_id=city_id,
                    zone_id_id=zone_id,
                    panchayat_id_id=panchayat_id,
                    ward_id_id=ward_id,
                    mainscreen_id_id=mainscreen_id,
                    permission_type=permission_type,
                    userscreen_id_id=screen_id,
                    userscreenaction_id_id=action_id,
                    order_no=order_no,
                    description=screen_desc,
                    is_deleted=False,
                    is_active=True,
                )
                created.append(permission)

            if "columnIds" in screen and screen["columnIds"] is not None:
                result = self._sync_column_permissions(
                    company_id=company_id,
                    project_id=project_id,
                    userscreen_id=screen_id,
                    column_permissions=screen.get("columnPermissions"),
                    column_ids=screen["columnIds"],
                    description=screen_desc,
                )
                created_columns.extend(result["created"])
                updated_columns.extend(result["updated"])
                deleted_columns.extend(result["deleted"])

        for key, permission in existing_lookup.items():
            if key not in incoming_action_keys and not permission.is_deleted:
                permission.is_deleted = True
                permission.is_active = False
                permission.save(update_fields=["is_deleted", "is_active", "updated_at"])
                deleted.append(permission)

        return {
            "created": created,
            "updated": updated,
            "deleted": deleted,
            "created_columns": created_columns,
            "updated_columns": updated_columns,
            "deleted_columns": deleted_columns,
        }

    def _sync_column_permissions(
        self,
        *,
        company_id,
        project_id,
        userscreen_id,
        column_ids,
        column_permissions,
        description,
    ):
        existing = {
            obj.column_id_id: obj
            for obj in CompanyUserScreenColumnPermission.objects.filter(
                company_id_id=company_id,
                project_id_id=project_id,
                userscreen_id_id=userscreen_id,
            )
        }

        if column_permissions is None:
            column_permissions = [
                {"column_id": column_id, "can_view": True, "order_no": index}
                for index, column_id in enumerate(column_ids, start=1)
            ]

        incoming = {item["column_id"] for item in column_permissions}
        created = []
        updated = []
        deleted = []

        for fallback_order_no, column_permission in enumerate(column_permissions, start=1):
            column_id = column_permission["column_id"]
            order_no = column_permission.get("order_no") or fallback_order_no
            can_view = bool(column_permission.get("can_view", True))
            permission = existing.get(column_id)
            if permission:
                permission.can_view = can_view
                permission.order_no = order_no
                permission.description = description
                permission.is_deleted = False
                permission.is_active = True
                permission.updated_at = timezone.now()
                updated.append(permission)
                continue

            created.append(
                CompanyUserScreenColumnPermission(
                    company_id_id=company_id,
                    project_id_id=project_id,
                    userscreen_id_id=userscreen_id,
                    column_id_id=column_id,
                    can_view=can_view,
                    order_no=order_no,
                    description=description,
                    is_deleted=False,
                    is_active=True,
                )
            )

        for column_id, permission in existing.items():
            if column_id not in incoming and not permission.is_deleted:
                permission.is_deleted = True
                permission.is_active = False
                permission.updated_at = timezone.now()
                deleted.append(permission)

        if created:
            CompanyUserScreenColumnPermission.objects.bulk_create(created)
        if updated:
            CompanyUserScreenColumnPermission.objects.bulk_update(
                updated,
                ["can_view", "order_no", "description", "is_deleted", "is_active", "updated_at"],
            )
        if deleted:
            CompanyUserScreenColumnPermission.objects.bulk_update(
                deleted,
                ["is_deleted", "is_active", "updated_at"],
            )

        return {"created": created, "updated": updated, "deleted": deleted}
