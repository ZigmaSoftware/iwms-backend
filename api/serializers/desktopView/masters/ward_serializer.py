from rest_framework import serializers
from api.apps.ward import Ward

class WardSerializer(serializers.ModelSerializer):
    continent_name = serializers.CharField(source='continent_id.name', read_only=True)
    country_name = serializers.CharField(source='country_id.name', read_only=True)
    state_name = serializers.CharField(source='state_id.name', read_only=True)
    district_name = serializers.CharField(source='district_id.name', read_only=True)
    city_name = serializers.CharField(source='city_id.name', read_only=True)
    zone_name = serializers.CharField(source='zone_id.name', read_only=True)

    class Meta:
        model = Ward
        fields = '__all__'
        read_only_fields = ["unique_id"]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        def cur(field):
            return attrs.get(field, getattr(instance, field) if instance else None)

        name = (attrs.get("name") or (instance.name if instance else "")).strip()
        country, state, district, city, zone = [cur(f) for f in ["country_id","state_id","district_id","city_id","zone_id"]]
        if not name:
            return attrs

        qs = Ward.objects.filter(is_deleted=False, name__iexact=name)
        for field, value in {"country_id":country,"state_id":state,"district_id":district,"city_id":city,"zone_id":zone}.items():
            qs = qs.filter(**({f"{field}": value} if value else {f"{field}__isnull": True}))
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError({"name": "Ward name already exists in the selected scope."})
        attrs["name"] = name
        return attrs
