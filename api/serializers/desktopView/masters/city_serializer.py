from rest_framework import serializers
from api.apps.city import City

class CitySerializer(serializers.ModelSerializer):
    continent_name = serializers.CharField(
        source="continent_id.name",
        read_only=True
    )
    country_name = serializers.CharField(
        source="country_id.name",
        read_only=True
    )
    state_name = serializers.CharField(
        source="state_id.name",
        read_only=True
    )
    district_name = serializers.CharField(
        source="district_id.name",
        read_only=True
    )

    class Meta:
        model = City
        fields = "__all__"
        read_only_fields = ["unique_id"]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        # District FK is district_id from model
        district = attrs.get("district_id") or (instance.district_id if instance else None)
        name = attrs.get("name") or (instance.name if instance else None)

        if not name:
            return attrs

        name_clean = name.strip()

        qs = City.objects.filter(
            district_id=district,
            name__iexact=name_clean,
            is_deleted=False,
        )

        if instance:
            qs = qs.exclude(unique_id=instance.unique_id)

        if qs.exists():
            raise serializers.ValidationError({
                "name": "City name already exists in this district."
            })

        attrs["name"] = name_clean
        return attrs
