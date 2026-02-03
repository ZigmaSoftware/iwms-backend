from rest_framework import serializers
from django.contrib.auth.hashers import check_password, identify_hasher
from django.db.models import Q
from api.apps.staffcreation import StaffOfficeDetails
from api.apps.customercreation import CustomerCreation


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

        user = None

        # First try to find in CustomerCreation
        customers = (
            CustomerCreation.objects
            .filter(is_active=True, is_deleted=False, is_superuser=False)
            .filter(
                Q(username__iexact=username)
                | Q(customer_name__iexact=username)
                | Q(contact_no__iexact=username)
            )
        )

        for customer in customers:
            if self._password_matches(password, customer.password):
                user = customer
                break

        # If not found, try StaffOfficeDetails
        if not user:
            staff_candidates = (
                StaffOfficeDetails.objects
                .select_related("user_type_id", "staffusertype_id", "personal_details")
                .filter(is_active=True, is_deleted=False, is_superuser=False)
                .filter(
                    Q(username__iexact=username)
                    | Q(employee_name__iexact=username)
                    | Q(staff_unique_id__iexact=username)
                    | Q(personal_details__contact_email__iexact=username)
                )
            )

            for staff in staff_candidates:
                if self._password_matches(password, staff.password):
                    user = staff
                    break

        if not user:
            raise serializers.ValidationError("Invalid username or password")

        # USER TYPE VALIDATION
        if hasattr(user, 'user_type_id') and user.user_type_id:
            user_type = user.user_type_id.name.lower()
        else:
            # Default to customer for CustomerCreation objects
            user_type = "customer" if hasattr(user, 'customer_name') else "staff"

        if user_type == "customer":
            if not hasattr(user, 'customer_name'):
                raise serializers.ValidationError("Customer profile not found")

        elif user_type == "staff":
            if not hasattr(user, 'employee_name'):
                raise serializers.ValidationError("Staff details missing")
            if not user.staffusertype_id:
                raise serializers.ValidationError("Staff role not assigned")

        else:
            raise serializers.ValidationError("Unsupported user role type")

        attrs["user"] = user
        attrs["user_type"] = user_type
        return attrs
