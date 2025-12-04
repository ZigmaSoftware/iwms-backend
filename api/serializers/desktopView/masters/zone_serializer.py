from rest_framework import serializers
from api.apps.zone import Zone

class ZoneSerializer(serializers.ModelSerializer):
    continent_name = serializers.CharField(source='continent_id.name', read_only=True)
    country_name = serializers.CharField(source='country_id.name', read_only=True)
    state_name = serializers.CharField(source='state_id.name', read_only=True)
    district_name = serializers.CharField(source='district_id.name', read_only=True)
    city_name = serializers.CharField(source='city_id.name', read_only=True)

    class Meta:
        model = Zone
        fields = '__all__'
        read_only_fields = ["unique_id"]

    def validate(self, attrs):
        # Handle PATCH safely
        instance = getattr(self, "instance", None)

        # Extract values with fallback to instance (for PATCH)
        city = attrs.get("city_id", getattr(instance, "city_id", None))
        name = attrs.get("name", getattr(instance, "name", None))

        # If either field is missing in PATCH, still safe
        if name is None or city is None:
            return attrs

        # Validate duplication
        cleaned_name = name.strip()
        qs = Zone.objects.filter(
            city_id=city,
            name__iexact=cleaned_name,
            is_deleted=False
        )

        if instance:
            qs = qs.exclude(pk=instance.pk)

        if qs.exists():
            raise serializers.ValidationError({
                "name": "Zone name already exists for the selected city."
            })

        attrs["name"] = cleaned_name
        return attrs
