from rest_framework import serializers
from api.apps.userCreation import User
from api.apps.userType import UserType
from api.serializers.desktopView.users.customer_nested_serializer import CustomerNestedSerializer


class UserSerializer(serializers.ModelSerializer):

    # ---------- READ-ONLY DISPLAY FIELDS ----------
    user_type_name = serializers.CharField(source="user_type.name", read_only=True)
    staffusertype_name = serializers.CharField(source="staffusertype_id.name", read_only=True)
    staff_name = serializers.CharField(source="staff_id.name", read_only=True)
    customer = CustomerNestedSerializer(source="customer_id", read_only=True)
    district_name = serializers.CharField(source="district_id.name", read_only=True)
    city_name = serializers.CharField(source="city_id.name", read_only=True)
    zone_name = serializers.CharField(source="zone_id.name", read_only=True)
    ward_name = serializers.CharField(source="ward_id.name", read_only=True)
    

    class Meta:
        model = User
        fields = "__all__"

    # ---------- VALIDATION (MANDATORY & RESTRICTED FIELDS) ----------
    def validate(self, attrs):
        user_type = attrs.get("user_type")

        # If no user_type provided, skip validation
        if not user_type:
            return attrs

        name = user_type.name.lower().strip()

        # ======================================================
        # USER TYPE = CUSTOMER
        # ======================================================
        if name == "customer":

            # Mandatory
            if not attrs.get("customer_id"):
                raise serializers.ValidationError({
                    "customer_id": "customer_id is required when user type is Customer."
                })

            # These fields must be null
            if attrs.get("staffusertype_id") or attrs.get("staff_id"):
                raise serializers.ValidationError(
                    "Staff fields are not allowed for Customer."
                )

        # ======================================================
        # USER TYPE = STAFF
        # ======================================================
        if name == "staff":

            # Mandatory
            if not attrs.get("staffusertype_id"):
                raise serializers.ValidationError({
                    "staffusertype_id": "staffusertype_id is required when user type is Staff."
                })

            if not attrs.get("staff_id"):
                raise serializers.ValidationError({
                    "staff_id": "staff_id is required when user type is Staff."
                })

            # Not allowed
            if attrs.get("customer_id"):
                raise serializers.ValidationError(
                    "customer_id is not allowed when user type is Staff."
                )

        return attrs
