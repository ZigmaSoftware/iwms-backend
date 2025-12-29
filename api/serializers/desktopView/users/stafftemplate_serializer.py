from rest_framework import serializers
from api.apps.stafftemplate import StaffTemplate


class StaffTemplateSerializer(serializers.ModelSerializer):

    primary_driver_name = serializers.CharField(
        source="primary_driver_id.staffusertype_id.name",
        read_only=True
    )
    primary_operator_name = serializers.CharField(
        source="primary_operator_id.staffusertype_id.name",
        read_only=True
    )

    class Meta:
        model = StaffTemplate
        fields = [
            "unique_id",

            "primary_driver_id",
            "primary_driver_name",
            "secondary_driver_id",

            "primary_operator_id",
            "primary_operator_name",
            "secondary_operator_id",

            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "is_deleted",
            "created_at",
            "updated_at",
            "primary_driver_name",
            "primary_operator_name",
        ]

    def validate(self, attrs):
        """
        STRICT ROLE ENFORCEMENT
        - Drivers → staffusertype.name == 'driver'
        - Operators → staffusertype.name == 'operator'
        - No duplicate user across roles
        """

        instance = getattr(self, "instance", None)

        def resolve(field_name):
            if field_name in attrs:
                return attrs.get(field_name)
            return getattr(instance, field_name) if instance else None

        def validate_role(user, expected_role, field_name):
            if not user:
                return

            if not user.staffusertype_id:
                raise serializers.ValidationError({
                    field_name: "User has no staff role assigned"
                })

            actual_role = user.staffusertype_id.name
            if actual_role != expected_role:
                raise serializers.ValidationError({
                    field_name: f"Only '{expected_role}' role allowed. Found '{actual_role}'."
                })

        # ---- ROLE CHECKS ----
        validate_role(resolve("primary_driver_id"), "driver", "primary_driver_id")
        validate_role(resolve("secondary_driver_id"), "driver", "secondary_driver_id")

        validate_role(resolve("primary_operator_id"), "operator", "primary_operator_id")
        validate_role(resolve("secondary_operator_id"), "operator", "secondary_operator_id")

        # ---- DUPLICATE PREVENTION ----
        users = [
            resolve("primary_driver_id"),
            resolve("secondary_driver_id"),
            resolve("primary_operator_id"),
            resolve("secondary_operator_id"),
        ]
        user_ids = [
            getattr(user, "unique_id", user)
            for user in users
            if user
        ]

        if len(user_ids) != len(set(user_ids)):
            raise serializers.ValidationError(
                "Same user cannot be assigned to multiple roles in a staff template."
            )

        return attrs
