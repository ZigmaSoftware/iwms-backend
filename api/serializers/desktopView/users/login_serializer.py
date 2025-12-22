from rest_framework import serializers
from django.db.models import Q
from api.apps.userCreation import User
from api.apps.userscreenpermission import UserScreenPermission


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        
        username = attrs["username"].strip()
        password = attrs["password"].strip()

        # FIND USER BY MULTIPLE MATCH FIELDS
        user = (
            User.objects
            .select_related("user_type", "staffusertype_id", "staff_id", "customer_id","staff_id__personal_details")
            .filter(is_active=True, is_deleted=False)
            .filter(
                Q(customer_id__customer_name__iexact=username) |
                Q(customer_id__contact_no__iexact=username) |
                Q(staff_id__employee_name__iexact=username) |
                Q(staff_id__staff_unique_id__iexact=username) |
                Q(unique_id__iexact=username) |
                Q(staff_id__personal_details__contact_email__iexact=username) 
            )
            .first()
        )

        if not user:
            raise serializers.ValidationError("Invalid username or password")

        if password != user.password:
            raise serializers.ValidationError("Invalid username or password")

        # --------------------------
        # USER TYPE VALIDATION
        # --------------------------
        utype = user.user_type.name.lower()

        if utype == "customer":
            if not user.customer_id:
                raise serializers.ValidationError("Customer profile not found")
            staffusertype_id = None

        elif utype == "staff":
            if not user.staff_id:
                raise serializers.ValidationError("Staff details missing")
            if not user.staffusertype_id:
                raise serializers.ValidationError("Staff role not assigned")

            staffusertype_id = user.staffusertype_id.unique_id

        else:
            raise serializers.ValidationError("Unsupported user role type")

        # --------------------------------
        # FETCH PERMISSIONS FOR THIS ROLE
        # --------------------------------
        queryset = UserScreenPermission.objects.filter(
            usertype_id_id=user.user_type.unique_id,
            staffusertype_id_id=staffusertype_id,
            is_deleted=False,
            is_active=True
        ).select_related(
            "mainscreen_id",
            "userscreen_id",
            "userscreenaction_id"
        ).order_by("order_no")

        # Format permissions
        permissions = {}
        for perm in queryset:
            main_name = perm.mainscreen_id.mainscreen_name
            screen_name = perm.userscreen_id.userscreen_name
            action_name = perm.userscreenaction_id.action_name

            if main_name not in permissions:
                permissions[main_name] = {}

            if screen_name not in permissions[main_name]:
                permissions[main_name][screen_name] = []

            permissions[main_name][screen_name].append(action_name)

        if not permissions and utype == "staff":
            staff_role = user.staffusertype_id.name.lower()
            if staff_role in ["driver", "operator"]:
                permissions = {
                    "role-assign": {
                        "Assignments": ["view", "add"],
                        "DailyAssignments": ["view", "add"],
                        "StaffAssignments": ["view"],
                        "CollectionLogs": ["add"],
                    },
                    "customers": {
                        "Customercreations": ["view"],
                    },
                }

        attrs["user"] = user
        attrs["permissions"] = permissions

        return attrs

    
