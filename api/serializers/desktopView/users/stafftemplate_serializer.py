from rest_framework import serializers

from api.apps.stafftemplate import StaffTemplate
from api.apps.userCreation import User
from api.serializers.desktopView.users.user_serializer import UniqueIdOrPkField


class CommaSeparatedListField(serializers.ListField):
    """
    Accepts comma-separated strings or repeated form-data keys and
    normalises them into a clean list.
    """

    def to_internal_value(self, data):
        if isinstance(data, str):
            data = [item.strip() for item in data.split(",") if item.strip()]
        elif isinstance(data, (list, tuple)):
            normalized = []
            for item in data:
                if item in ("", None):
                    continue
                if isinstance(item, str):
                    normalized.extend([part.strip() for part in item.split(",") if part.strip()])
                else:
                    normalized.append(item)
            data = normalized
        return super().to_internal_value(data)

    def to_representation(self, value):
        if value is None:
            return []
        return super().to_representation(value)


class BlankableUniqueIdField(UniqueIdOrPkField):
    """
    Treat empty strings as null so optional FK fields don't fail validation.
    """

    def to_internal_value(self, data):
        if data in ("", None):
            return None
        return super().to_internal_value(data)


class StaffTemplateSerializer(serializers.ModelSerializer):

    driver_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=User.objects.filter(is_deleted=False),
    )
    operator_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=User.objects.filter(is_deleted=False),
    )
    created_by = BlankableUniqueIdField(
        slug_field="unique_id",
        queryset=User.objects.filter(is_deleted=False),
        required=False,
    )
    updated_by = BlankableUniqueIdField(
        slug_field="unique_id",
        queryset=User.objects.filter(is_deleted=False),
        required=False,
    )
    approved_by = BlankableUniqueIdField(
        slug_field="unique_id",
        queryset=User.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )

    driver_name = serializers.SerializerMethodField()
    operator_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()

    extra_operator_id = CommaSeparatedListField(child=serializers.CharField(), required=False, allow_empty=True)

    class Meta:
        model = StaffTemplate
        fields = [
            "id",
            "unique_id",

            "driver_id",
            "driver_name",
            "operator_id",
            "operator_name",
            "extra_operator_id",

            "created_by",
            "created_by_name",
            "updated_by",
            "updated_by_name",
            "approved_by",
            "approved_by_name",

            "status",
            "approval_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "unique_id",
            "created_at",
            "updated_at",
            "driver_name",
            "operator_name",
            "created_by_name",
            "updated_by_name",
            "approved_by_name",
        ]

    def validate(self, attrs):
        """
        STRICT ROLE ENFORCEMENT
        - Driver → staffusertype.name == 'driver'
        - Operator → staffusertype.name == 'operator'
        - No duplicate user across roles or extra operators
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
            if actual_role.lower() != expected_role:
                raise serializers.ValidationError({
                    field_name: f"Only '{expected_role}' role allowed. Found '{actual_role}'."
                })

        driver = resolve("driver_id")
        operator = resolve("operator_id")

        # ---- ROLE CHECKS ----
        validate_role(driver, "driver", "driver_id")
        validate_role(operator, "operator", "operator_id")

        # ---- DUPLICATE PREVENTION ----
        if driver and operator and driver.unique_id == operator.unique_id:
            raise serializers.ValidationError(
                {"operator_id": "Driver and operator must be different users."}
            )

        extra_operator_ids = attrs.get("extra_operator_id")
        if extra_operator_ids is None and instance:
            extra_operator_ids = instance.extra_operator_id

        if extra_operator_ids is not None:
            if not isinstance(extra_operator_ids, list):
                raise serializers.ValidationError(
                    {"extra_operator_id": "Expected a list of user IDs."}
                )

            extra_ids = [str(item) for item in extra_operator_ids if item]
            if len(extra_ids) != len(set(extra_ids)):
                raise serializers.ValidationError(
                    {"extra_operator_id": "Duplicate users are not allowed."}
                )

            if operator and operator.unique_id in extra_ids:
                raise serializers.ValidationError(
                    {"extra_operator_id": "Extra operators cannot include the primary operator."}
                )

            if driver and driver.unique_id in extra_ids:
                raise serializers.ValidationError(
                    {"extra_operator_id": "Extra operators cannot include the driver."}
                )

            if extra_ids:
                operators = User.objects.filter(
                    unique_id__in=extra_ids,
                    is_deleted=False,
                )
                found_ids = {user.unique_id for user in operators}
                missing_ids = sorted(set(extra_ids) - found_ids)
                if missing_ids:
                    raise serializers.ValidationError({
                        "extra_operator_id": (
                            f"Unknown user IDs: {', '.join(missing_ids)}."
                        )
                    })

                non_operators = [
                    user.unique_id
                    for user in operators
                    if not user.staffusertype_id
                    or user.staffusertype_id.name.lower() != "operator"
                ]
                if non_operators:
                    raise serializers.ValidationError({
                        "extra_operator_id": (
                            "Only 'operator' role allowed in extra_operator_id."
                        )
                    })

        return attrs

    def _resolve_staff_name(self, user):
        if not user:
            return None
        staff = getattr(user, "staff_id", None)
        if staff and getattr(staff, "employee_name", None):
            return staff.employee_name
        return getattr(user, "username", None) or getattr(user, "unique_id", None)

    def get_driver_name(self, obj):
        return self._resolve_staff_name(getattr(obj, "driver_id", None))

    def get_operator_name(self, obj):
        return self._resolve_staff_name(getattr(obj, "operator_id", None))

    def get_created_by_name(self, obj):
        return self._resolve_staff_name(getattr(obj, "created_by", None))

    def get_updated_by_name(self, obj):
        return self._resolve_staff_name(getattr(obj, "updated_by", None))

    def get_approved_by_name(self, obj):
        return self._resolve_staff_name(getattr(obj, "approved_by", None))
