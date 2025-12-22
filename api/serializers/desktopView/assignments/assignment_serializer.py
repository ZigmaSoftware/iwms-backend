from rest_framework import serializers

from api.apps.assignment import (
    DailyAssignment,
    AssignmentStatusHistory,
    DriverCollectionLog,
)
from api.apps.customercreation import CustomerCreation
from api.apps.userCreation import User
from api.apps.ward import Ward
from api.serializers.desktopView.users.user_serializer import UniqueIdOrPkField


class DailyAssignmentSerializer(serializers.ModelSerializer):

    ward = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=Ward.objects.filter(is_deleted=False),
    )

    customer = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=CustomerCreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )

    driver = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=User.objects.filter(is_deleted=False),
    )

    operator = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=User.objects.filter(is_deleted=False),
    )

    assigned_by = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=User.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )

    ward_name = serializers.CharField(source="ward.name", read_only=True)
    customer_name = serializers.CharField(
        source="customer.customer_name", read_only=True
    )

    driver_name = serializers.CharField(
        source="driver.staff_id.employee_name", read_only=True
    )
    operator_name = serializers.CharField(
        source="operator.staff_id.employee_name", read_only=True
    )

    assigned_by_name = serializers.CharField(
        source="assigned_by.staff_id.employee_name", read_only=True
    )

    class Meta:
        model = DailyAssignment
        fields = [
            "id",
            "unique_id",
            "date",
            "ward",
            "ward_name",
            "customer",
            "customer_name",
            "driver",
            "driver_name",
            "operator",
            "operator_name",
            "assignment_type",
            "shift",
            "assigned_by",
            "assigned_by_name",
            "current_status",
            "driver_status",
            "operator_status",
            "driver_completed_at",
            "operator_completed_at",
            "completed_at",
            "skipped_at",
            "skip_reason",
            "cancelled_at",
            "cancelled_reason",
            "created_at",
            "updated_at",
            "is_active",
        ]

        read_only_fields = [
            "id",
            "unique_id",
            "created_at",
            "updated_at",
            "current_status",
            "driver_status",
            "operator_status",
            "driver_completed_at",
            "operator_completed_at",
            "completed_at",
            "skipped_at",
            "skip_reason",
            "cancelled_at",
            "cancelled_reason",
        ]

    def validate(self, attrs):
        driver = attrs.get("driver")
        operator = attrs.get("operator")
        customer = attrs.get("customer")

        errors = {}

        if driver and driver.staffusertype_id.name.lower() != "driver":
            errors["driver"] = "Selected user is not a driver."

        if operator and operator.staffusertype_id.name.lower() != "operator":
            errors["operator"] = "Selected user is not an operator."

        if customer and attrs.get("assignment_type") == "primary":
            errors["customer"] = (
                "Customer assignment allowed only for temporary/emergency."
            )

        if errors:
            raise serializers.ValidationError(errors)

        return attrs


class AssignmentStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(
        source="changed_by.staff_id.employee_name", read_only=True
    )

    class Meta:
        model = AssignmentStatusHistory
        fields = [
            "id",
            "assignment",
            "status",
            "changed_by",
            "changed_by_name",
            "reason",
            "metadata",
            "timestamp",
            "latitude",
            "longitude",
        ]
        read_only_fields = ["id", "timestamp"]


class DriverCollectionLogSerializer(serializers.ModelSerializer):
    assignment = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=DailyAssignment.objects.all(),
    )
    driver = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=User.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    driver_name = serializers.CharField(
        source="driver.staff_id.employee_name", read_only=True
    )

    class Meta:
        model = DriverCollectionLog
        fields = [
            "id",
            "assignment",
            "driver",
            "driver_name",
            "action",
            "skip_reason",
            "waste_weight",
            "photo_url",
            "latitude",
            "longitude",
            "timestamp",
            "notes",
        ]
        read_only_fields = ["id", "timestamp"]


class EnhancedAssignmentSerializer(serializers.ModelSerializer):
    """
    Detailed assignment serializer with history and logs.
    """

    ward_name = serializers.CharField(source="ward.name", read_only=True)
    driver_name = serializers.CharField(
        source="driver.staff_id.employee_name", read_only=True
    )
    operator_name = serializers.CharField(
        source="operator.staff_id.employee_name", read_only=True
    )

    status_history = AssignmentStatusHistorySerializer(many=True, read_only=True)
    collection_logs = DriverCollectionLogSerializer(many=True, read_only=True)
    total_status_changes = serializers.IntegerField(read_only=True)
    latest_action = serializers.SerializerMethodField()

    class Meta:
        model = DailyAssignment
        fields = [
            "id",
            "unique_id",
            "date",
            "ward",
            "ward_name",
            "driver",
            "driver_name",
            "operator",
            "operator_name",
            "assignment_type",
            "shift",
            "current_status",
            "driver_status",
            "operator_status",
            "driver_completed_at",
            "operator_completed_at",
            "created_at",
            "updated_at",
            "completed_at",
            "skipped_at",
            "skip_reason",
            "cancelled_at",
            "cancelled_reason",
            "is_active",
            "status_history",
            "collection_logs",
            "total_status_changes",
            "latest_action",
        ]

    def get_latest_action(self, obj):
        latest = obj.status_history.first()
        if latest:
            changed_by_name = None
            if latest.changed_by and getattr(latest.changed_by, "staff_id", None):
                changed_by_name = latest.changed_by.staff_id.employee_name
            return {
                "status": latest.status,
                "timestamp": latest.timestamp,
                "changed_by": changed_by_name,
            }
        return None
