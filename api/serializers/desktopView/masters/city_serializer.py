from rest_framework import serializers
from api.apps.city import City

class CitySerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    state_name = serializers.CharField(source='state.name', read_only=True)
    district_name = serializers.CharField(source='district.name', read_only=True)

    class Meta:
        model = City
        fields = "__all__"

    def validate(self, attrs):
        """
        Prevent duplicate city name for the same district.
        PATCH should not fail when only is_active is updated.
        """

        instance = getattr(self, "instance", None)

        # Fetch existing values if not provided (PATCH support)
        name = attrs.get("name") or (instance.name if instance else None)
        district = attrs.get("district") or (instance.district if instance else None)

        # If name is still None → no validation needed (PATCH for is_active only)
        if not name:
            return attrs

        clean_name = name.strip()

        # Duplicate check
        qs = City.objects.filter(
            district=district,
            name__iexact=clean_name,
            is_deleted=False
        )

        # Exclude self while updating
        if instance:
            qs = qs.exclude(id=instance.id)

        if qs.exists():
            raise serializers.ValidationError({
                "name": "City name already exists for the selected district."
            })

        # Clean name before saving
        attrs["name"] = clean_name
        return attrs
