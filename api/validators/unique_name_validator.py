from rest_framework import serializers

def unique_name_validator(Model, name_field="name", scope_fields=None):
    """
    Model: Model class
    name_field: DB column for the name
    scope_fields: list of FK field names to validate together
    """

    scope_fields = scope_fields or []

    def validate(serializer, attrs):
        instance = getattr(serializer, "instance", None)

        # resolve name
        name = attrs.get(name_field) or (getattr(instance, name_field) if instance else None)
        if not name:
            return attrs

        name_clean = name.strip()

        # base queryset with soft-delete awareness
        base_filter = {f"{name_field}__iexact": name_clean}
        # prefer is_deleted field; fallback to is_delete if that's what the model has
        if hasattr(Model, "is_deleted"):
            base_filter["is_deleted"] = False
        elif hasattr(Model, "is_delete"):
            base_filter["is_delete"] = False

        qs = Model.objects.filter(**base_filter)

        # apply scope filters
        for field in scope_fields:
            value = (
                attrs.get(field)
                or (getattr(instance, field) if instance else None)
            )
            if value:
                qs = qs.filter(**{field: value})
            else:
                qs = qs.filter(**{f"{field}__isnull": True})

        # exclude self
        if instance:
            qs = qs.exclude(pk=instance.pk)

        if qs.exists():
            raise serializers.ValidationError({
                name_field: f"{Model.__name__} `{name_clean}` already exists in the selected scope."
            })

        attrs[name_field] = name_clean
        return attrs

    return validate
