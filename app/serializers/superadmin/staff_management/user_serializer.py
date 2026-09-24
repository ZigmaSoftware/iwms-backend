from rest_framework import serializers


class UniqueIdOrPkField(serializers.Field):
    """
    Accept related object via its slug_field (unique_id by default, but
    some models' real identifier is a differently-named field — e.g.
    Staffcreation's is staff_unique_id). Serialize always as that same field.
    """

    def __init__(self, *args, queryset=None, slug_field=None, **kwargs):
        self._queryset = queryset
        self._slug_field = slug_field or "unique_id"
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        return self._queryset

    def to_representation(self, value):
        if value is None:
            return None
        if hasattr(value, self._slug_field):
            return getattr(value, self._slug_field)
        return str(value)

    def to_internal_value(self, data):
        value = str(data).strip() if data is not None else ""
        if not value:
            return None
        queryset = self.get_queryset()
        if queryset is None:
            raise serializers.ValidationError("Invalid reference value")
        obj = queryset.filter(**{self._slug_field: value}).first()
        if obj:
            return getattr(obj, self._slug_field)
        raise serializers.ValidationError("Invalid reference value")