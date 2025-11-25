from rest_framework import serializers
from api.apps.zone import Zone

class ZoneSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    state_name = serializers.CharField(source='state.name', read_only=True)
    district_name = serializers.CharField(source='district.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)

    class Meta:
        model = Zone
        fields = '__all__'

    def validate(self, attrs):
        # Handle PATCH safely
        instance = getattr(self, "instance", None)

        # Extract values with fallback to instance (for PATCH)
        city = attrs.get("city", getattr(instance, "city", None))
        name = attrs.get("name", getattr(instance, "name", None))

        # If either field is missing in PATCH, still safe
        if name is None or city is None:
            return attrs

        # Validate duplication
        qs = Zone.objects.filter(
            city=city,
            name__iexact=name.strip(),
            is_deleted=False
        )

        if instance:
            qs = qs.exclude(pk=instance.pk)

        if qs.exists():
            raise serializers.ValidationError({
                "name": "Zone name already exists for the selected city."
            })

        return attrs
