from rest_framework import serializers
from django.db.models import Q
from api.apps.userCreation import User


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        username = attrs["username"].strip()
        password = attrs["password"].strip()

        # FIND USER BY MULTIPLE MATCH FIELDS
        user = (
            User.objects
            .select_related(
                "user_type",
                "staffusertype_id",
                "staff_id",
                "customer_id",
            )
            .filter(is_active=True, is_delete=False)
            .filter(
                Q(customer_id__customer_name__iexact=username) |
                Q(customer_id__contact_no__iexact=username) |
                Q(staff_id__employee_name__iexact=username) |
                Q(staff_id__staff_unique_id__iexact=username) | 
                Q(unique_id__iexact=username)
            )
            .first()
        )

        if not user:
            raise serializers.ValidationError("Invalid username or password")

        # ---- FIXED PASSWORD CHECK (PLAIN TEXT) ----
        if password != user.password:
            raise serializers.ValidationError("Invalid username or password")

        # USER TYPE VALIDATION
        user_type = user.user_type.name.lower()

        if user_type == "customer":
            if not user.customer_id:
                raise serializers.ValidationError("Customer profile not found")

        elif user_type == "staff":
            if not user.staff_id:
                raise serializers.ValidationError("Staff details missing")
            if not user.staffusertype_id:
                raise serializers.ValidationError("Staff role not assigned")

        else:
            raise serializers.ValidationError("Unsupported user role type")

        attrs["user"] = user
        return attrs