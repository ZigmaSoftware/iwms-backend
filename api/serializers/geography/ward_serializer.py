from rest_framework import serializers
from ...apps.ward import Ward

class WardSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    state_name = serializers.CharField(source='state.name', read_only=True)
    district_name = serializers.CharField(source='district.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)
    zone_name = serializers.CharField(source='zone.name', read_only=True)

    class Meta:
        model = Ward
        fields = '__all__'

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        def cur(field):
            return attrs.get(field, getattr(instance, field) if instance else None)

        name = (attrs.get("name") or (instance.name if instance else "")).strip()
        country, state, district, city, zone = [cur(f) for f in ["country","state","district","city","zone"]]
        if not name:
            return attrs

        qs = Ward.objects.filter(is_deleted=False, name__iexact=name)
        for field, value in {"country":country,"state":state,"district":district,"city":city,"zone":zone}.items():
            qs = qs.filter(**({f"{field}": value} if value else {f"{field}__isnull": True}))
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError({"name": "Ward name already exists in the selected scope."})
        return attrs
