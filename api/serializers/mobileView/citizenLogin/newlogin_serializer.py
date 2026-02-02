from rest_framework import serializers
from django.contrib.auth.hashers import check_password, identify_hasher
from django.db.models import Q
from api.apps.userCreation import User


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    @staticmethod
    def _password_matches(raw_password, stored_password):
        if stored_password is None:
            return False
        try:
            identify_hasher(stored_password)
        except ValueError:
            return raw_password == stored_password
        return check_password(raw_password, stored_password)

    def validate(self, attrs):
        username = attrs["username"].strip()
        password = attrs["password"].strip()

        # FIND USER BY MULTIPLE MATCH FIELDS
        candidates = (
            User.objects.select_related(
                "user_type_id",
                "staffusertype_id",
                "staff_id",
                "customer_id",
                "staff_id__personal_details",
            )
            .filter(is_active=True, is_deleted=False, is_superuser=False)
            .filter(
                Q(username__iexact=username)
                | Q(customer_id__customer_name__iexact=username)
                | Q(customer_id__contact_no__iexact=username)
                | Q(staff_id__employee_name__iexact=username)
                | Q(staff_id__staff_unique_id__iexact=username)
                | Q(unique_id__iexact=username)
                | Q(staff_id__personal_details__contact_email__iexact=username)
            )
        )

        user = None
        for candidate in candidates:
            if self._password_matches(password, candidate.password):
                user = candidate
                break

        if not user:
            raise serializers.ValidationError("Invalid username or password")

        # USER TYPE VALIDATION
        if not user.user_type_id:
            raise serializers.ValidationError("Unsupported user role type")

        user_type = user.user_type_id.name.lower()

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
