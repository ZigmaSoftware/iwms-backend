# =========================================================
# serializers/screen_managements/companyuserscreencolumnpermission_serializer.py
# =========================================================

from rest_framework import serializers

from app.models.screen_managements.companyuserscreencolumnpermission import CompanyUserScreenColumnPermission
from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission
from app.models.screen_managements.userscreencolumn import UserScreenColumn


# ---------------------------------------------------------
# BASIC SERIALIZER
# ---------------------------------------------------------

class CompanyUserScreenColumnPermissionSerializer(serializers.ModelSerializer):
    """
    Serializer for CompanyUserScreenColumnPermission model.
    """

    # Related field names for better readability
    column_name = serializers.CharField(source="userscreencolumn_id.column_name", read_only=True)
    userscreen_name = serializers.CharField(source="companyuserscreenpermission_id.userscreen_id.userscreen_name", read_only=True)
    action_name = serializers.CharField(source="companyuserscreenpermission_id.userscreenaction_id.action_name", read_only=True)
    company_name = serializers.CharField(source="companyuserscreenpermission_id.company_id.name", read_only=True)

    class Meta:
        model = CompanyUserScreenColumnPermission
        fields = "__all__"


# ---------------------------------------------------------
# INPUT SERIALIZER FOR BULK OPERATIONS
# ---------------------------------------------------------

class ColumnPermissionInputSerializer(serializers.Serializer):
    """
    Input serializer for column permissions in bulk operations.
    """
    column_id = serializers.CharField()
    can_view = serializers.BooleanField(default=True)
    can_edit = serializers.BooleanField(default=False)
    can_filter = serializers.BooleanField(default=True)
    can_search = serializers.BooleanField(default=True)
    can_sort = serializers.BooleanField(default=True)
    order_no = serializers.IntegerField(default=1, required=False)
    description = serializers.CharField(required=False, allow_blank=True)

    def validate_column_id(self, value):
        """Validate that the column exists and is active."""
        try:
            column = UserScreenColumn.objects.get(unique_id=value, is_deleted=False)
            return column.unique_id
        except UserScreenColumn.DoesNotExist:
            raise serializers.ValidationError("Invalid column ID")


# ---------------------------------------------------------
# EXTENDED SERIALIZER WITH VALIDATION
# ---------------------------------------------------------

class CompanyUserScreenColumnPermissionCreateSerializer(serializers.Serializer):
    """
    Serializer for creating column permissions with validation.
    """
    companyuserscreenpermission_id = serializers.CharField()
    column_permissions = ColumnPermissionInputSerializer(many=True)

    def validate_companyuserscreenpermission_id(self, value):
        """Validate that the parent action permission exists."""
        try:
            permission = CompanyUserScreenPermission.objects.get(
                unique_id=value,
                is_deleted=False
            )
            return permission.unique_id
        except CompanyUserScreenPermission.DoesNotExist:
            raise serializers.ValidationError("Invalid action permission ID")

    def validate(self, data):
        """Cross-field validation."""
        permission_id = data["companyuserscreenpermission_id"]

        # Get all column IDs from input
        column_ids = [cp["column_id"] for cp in data["column_permissions"]]

        if not column_ids:
            raise serializers.ValidationError({"column_permissions": "At least one column permission required"})

        # Validate that all columns belong to the same userscreen as the action permission
        permission = CompanyUserScreenPermission.objects.get(unique_id=permission_id)
        userscreen_id = permission.userscreen_id_id

        valid_columns = set(
            UserScreenColumn.objects.filter(
                unique_id__in=column_ids,
                userscreen_id=userscreen_id,
                is_deleted=False
            ).values_list("unique_id", flat=True)
        )

        invalid_columns = set(column_ids) - valid_columns
        if invalid_columns:
            raise serializers.ValidationError({
                "column_permissions": f"Columns {', '.join(invalid_columns)} do not belong to the userscreen of this action permission"
            })

        return data

    def create(self, validated_data):
        permission_id = validated_data["companyuserscreenpermission_id"]
        column_permissions_data = validated_data["column_permissions"]

        created_permissions = []

        # Get existing column permissions for this action permission
        existing_permissions = CompanyUserScreenColumnPermission.objects.filter(
            companyuserscreenpermission_id=permission_id,
            is_deleted=False
        )

        existing_lookup = {
            obj.userscreencolumn_id_id: obj
            for obj in existing_permissions
        }

        incoming_column_ids = {cp["column_id"] for cp in column_permissions_data}

        # Process incoming permissions
        for cp_data in column_permissions_data:
            column_id = cp_data["column_id"]
            obj = existing_lookup.get(column_id)

            permission_data = {
                "companyuserscreenpermission_id_id": permission_id,
                "userscreencolumn_id_id": column_id,
                "can_view": cp_data.get("can_view", True),
                "can_edit": cp_data.get("can_edit", False),
                "can_filter": cp_data.get("can_filter", True),
                "can_search": cp_data.get("can_search", True),
                "can_sort": cp_data.get("can_sort", True),
                "order_no": cp_data.get("order_no", 1),
                "description": cp_data.get("description", ""),
                "is_deleted": False,
                "is_active": True,
            }

            if obj:
                # Update existing
                for key, value in permission_data.items():
                    setattr(obj, key, value)
                obj.save()
                created_permissions.append(obj)
            else:
                # Create new
                obj = CompanyUserScreenColumnPermission.objects.create(**permission_data)
                created_permissions.append(obj)

        # Soft delete permissions for columns that are no longer in the list
        for column_id, obj in existing_lookup.items():
            if column_id not in incoming_column_ids:
                obj.is_deleted = True
                obj.is_active = False
                obj.save(update_fields=["is_deleted", "is_active", "updated_at"])

        return created_permissions</content>
<parameter name="filePath">iwms-backend/app/serializers/screen_managements/companyuserscreencolumnpermission_serializer.py