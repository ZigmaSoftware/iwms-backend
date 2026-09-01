from rest_framework import serializers


class UniqueIdOrPkField(serializers.SlugRelatedField):
    """
    Accept related object via unique_id (slug) or numeric PK.
    Serialize always as unique_id.
    """

    def to_representation(self, value):
        return getattr(value, self.slug_field, None)

    def to_internal_value(self, data):
        try:
            return super().to_internal_value(data)
        except Exception:
            try:
                return self.get_queryset().get(pk=data)
            except Exception:
                raise serializers.ValidationError("Invalid reference value")
