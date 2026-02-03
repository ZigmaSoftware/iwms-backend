from rest_framework import serializers
from django.contrib.auth.hashers import check_password, identify_hasher
from django.db.models import Q
from api.apps.staffcreation import StaffOfficeDetails
from api.apps.customercreation import CustomerCreation
from api.apps.userscreenpermission import UserScreenPermission
from api.apps.userType import UserType


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    login_type = serializers.ChoiceField(
        choices=["staff", "customer"],
        default="staff",
        required=False
    )

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
        login_type = attrs.get("login_type", "staff")

        user = None
        permissions = {}
        user_type = None
        staffusertype_id = None

        if login_type == "staff":
            # Find staff by multiple match fields
            candidates = (
                StaffOfficeDetails.objects
                .select_related("user_type_id", "staffusertype_id", "personal_details")
                .filter(is_active=True, is_deleted=False, is_superuser=False)
                .filter(
                    Q(username__iexact=username) |
                    Q(employee_name__iexact=username) |
                    Q(staff_unique_id__iexact=username) |
                    Q(personal_details__contact_email__iexact=username)
                )
            )

            for candidate in candidates:
                if self._password_matches(password, candidate.password):
                    user = candidate
                    break

            if not user:
                raise serializers.ValidationError("Invalid username or password")

            if not user.user_type_id:
                raise serializers.ValidationError("Invalid user type")

            user_type = user.user_type_id.name.lower()

            if user_type == "staff":
                if not user.staffusertype_id:
                    raise serializers.ValidationError("Staff role not assigned")
                staffusertype_id = user.staffusertype_id.unique_id
            else:
                raise serializers.ValidationError("Unsupported user role type")

            # Fetch permissions for this role
            if staffusertype_id:
                queryset = UserScreenPermission.objects.filter(
                    usertype_id_id=user.user_type_id.unique_id,
                    staffusertype_id_id=staffusertype_id,
                    is_deleted=False,
                    is_active=True
                ).select_related(
                    "mainscreen_id",
                    "userscreen_id",
                    "userscreenaction_id"
                ).order_by("order_no")

                # Format permissions
                for perm in queryset:
                    main_name = perm.mainscreen_id.mainscreen_name
                    screen_name = perm.userscreen_id.userscreen_name
                    action_name = perm.userscreenaction_id.action_name

                    if main_name not in permissions:
                        permissions[main_name] = {}

                    if screen_name not in permissions[main_name]:
                        permissions[main_name][screen_name] = []

                    permissions[main_name][screen_name].append(action_name)

            # Add minimal defaults for driver/operator
            if user.staffusertype_id and user.staffusertype_id.name.lower() in ["driver", "operator"]:
                defaults = {
                    "customers": {
                        "Customercreations": ["view"],
                    },
                    "user-creation": {
                        "RoutePlan": ["add", "view", "edit", "delete"],
                        "AlternativeStaffTemplate": ["view"],
                    },
                }

                for module_name, screens in defaults.items():
                    module_perms = permissions.setdefault(module_name, {})
                    for screen_name, actions in screens.items():
                        existing = set(module_perms.get(screen_name, []))
                        module_perms[screen_name] = list(existing.union(actions))

        else:  # customer login
            candidates = (
                CustomerCreation.objects
                .filter(is_active=True, is_deleted=False, is_superuser=False)
                .filter(
                    Q(username__iexact=username) |
                    Q(customer_name__iexact=username) |
                    Q(contact_no__iexact=username)
                )
            )

            for candidate in candidates:
                if self._password_matches(password, candidate.password):
                    user = candidate
                    break

            if not user:
                raise serializers.ValidationError("Invalid username or password")

            # Get customer user type
            customer_user_type = UserType.objects.filter(name__iexact="customer").first()
            if customer_user_type:
                user_type = "customer"

        attrs["user"] = user
        attrs["permissions"] = permissions
        attrs["user_type"] = user_type
        attrs["staffusertype_id"] = staffusertype_id

        return attrs

    
