from rest_framework import serializers

from api.apps.assignment import DailyAssignment
from api.apps.customercreation import CustomerCreation
from api.apps.userCreation import User
from api.apps.ward import Ward
from api.serializers.desktopView.users.user_serializer import UniqueIdOrPkField


class DailyAssignmentSerializer(serializers.ModelSerializer):
    ward = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=Ward.objects.filter(is_deleted=False)
    )
    customer = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=CustomerCreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    driver = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=User.objects.filter(is_delete=False)
    )
    operator = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=User.objects.filter(is_delete=False)
    )

    assigned_by = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=User.objects.filter(is_delete=False),
        required=False,
        allow_null=True,
    )

    ward_name = serializers.CharField(source="ward.name", read_only=True)
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    customer_latitude = serializers.CharField(source="customer.latitude", read_only=True)
    customer_longitude = serializers.CharField(source="customer.longitude", read_only=True)
    driver_name = serializers.CharField(source="driver.staff_id.employee_name", read_only=True)
    operator_name = serializers.CharField(source="operator.staff_id.employee_name", read_only=True)
    assigned_by_name = serializers.CharField(source="assigned_by.staff_id.employee_name", read_only=True)

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
            "customer_latitude",
            "customer_longitude",
            "driver",
            "driver_name",
            "operator",
            "operator_name",
            "assigned_by",
            "assigned_by_name",
            "created_at",
            "updated_at",
            "is_active",
        ]
        read_only_fields = ["id", "unique_id", "date", "created_at", "updated_at"]

    def validate(self, attrs):
        driver = attrs.get("driver")
        operator = attrs.get("operator")
        errors = {}

        if driver and (not driver.staffusertype_id or driver.staffusertype_id.name.lower() != "driver"):
            errors["driver"] = "Selected user is not a driver."

        if operator and (not operator.staffusertype_id or operator.staffusertype_id.name.lower() != "operator"):
            errors["operator"] = "Selected user is not an operator."

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def create(self, validated_data):
        # date is auto_now_add
        return super().create(validated_data)
