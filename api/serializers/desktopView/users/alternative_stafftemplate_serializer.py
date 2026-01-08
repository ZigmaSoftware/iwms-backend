from rest_framework import serializers
from api.apps.alternative_staff_template import AlternativeStaffTemplate



class CommaSeparatedListField(serializers.ListField):
    """
    Accepts comma-separated strings or repeated form-data keys and
    normalises them into a clean list.
    """

    def to_internal_value(self, data):
        if isinstance(data, str):
            data = [item.strip() for item in data.split(",") if item.strip()]
        return super().to_internal_value(data)


class AlternativeStaffTemplateSerializer(serializers.ModelSerializer):
    extra_operator = CommaSeparatedListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    class Meta:
        model = AlternativeStaffTemplate
        fields = [
            'id',
            'unique_id',
            'staff_template',
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

            driver_id = str(getattr(driver, "pk", driver)) if driver else None
            operator_id = str(getattr(operator, "pk", operator)) if operator else None

            if driver_id and driver_id in extra_ids:
                raise serializers.ValidationError(
                    {"extra_operator": "Extra operators cannot include the driver."}
                )

            if operator_id and operator_id in extra_ids:
                raise serializers.ValidationError(
                    {"extra_operator": "Extra operators cannot include the primary operator."}
                )

            attrs["extra_operator"] = extra_ids

        return attrs
