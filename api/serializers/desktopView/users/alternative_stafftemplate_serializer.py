from rest_framework import serializers

from api.apps.alternative_staff_template import AlternativeStaffTemplate
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


class AlternativeStaffTemplateSerializer(serializers.ModelSerializer):
    staff_template = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=StaffTemplate.objects.all(),
    )
    driver = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=User.objects.filter(is_deleted=False),
    )
    operator = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=User.objects.filter(is_deleted=False),
    )
    requested_by = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=User.objects.filter(is_deleted=False),
        required=False,
    )
    approved_by = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=User.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    extra_operator = CommaSeparatedListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    staff_template_display_code = serializers.CharField(
        source="staff_template.display_code",
        read_only=True,
    )
    class Meta:
        model = AlternativeStaffTemplate
        fields = [
            'id',
            'unique_id',
            'staff_template',
            'staff_template_display_code',
            'effective_date',
            'driver',
            'operator',
            'extra_operator',
            'change_reason',
            'change_remarks',
            'requested_by',
            'approved_by',
            'approval_status',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'unique_id',
            'staff_template_display_code',
            'created_at',
        ]

    def validate(self, attrs):
        """
        Hard validation layer.
        Prevents obvious data-quality issues before hitting DB.
        """
        instance = getattr(self, "instance", None)

        def resolve(field_name):
            if field_name in attrs:
                return attrs.get(field_name)
            return getattr(instance, field_name) if instance else None

        driver = resolve("driver")
        operator = resolve("operator")

        if driver and operator and driver == operator:
            raise serializers.ValidationError(
                "Driver and Operator cannot be the same user."
            )

        extra_operator = attrs.get("extra_operator")
        if extra_operator is None and instance:
            extra_operator = instance.extra_operator

        if extra_operator is not None:
            if not isinstance(extra_operator, list):
                raise serializers.ValidationError(
                    {"extra_operator": "Expected a list of user IDs."}
                )

            extra_ids = [str(item) for item in extra_operator if item not in ("", None)]
            if len(extra_ids) != len(set(extra_ids)):
                raise serializers.ValidationError(
                    {"extra_operator": "Duplicate users are not allowed."}
                )

            driver_id = getattr(driver, "unique_id", None) if driver else None
            operator_id = getattr(operator, "unique_id", None) if operator else None

            if driver_id and driver_id in extra_ids:
                raise serializers.ValidationError(
                    {"extra_operator": "Extra operators cannot include the driver."}
                )

            if operator_id and operator_id in extra_ids:
                raise serializers.ValidationError(
                    {"extra_operator": "Extra operators cannot include the primary operator."}
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
                        "extra_operator": (
                            f"Unknown user IDs: {', '.join(missing_ids)}."
                        )
                    })

            attrs["extra_operator"] = extra_ids

        return attrs
