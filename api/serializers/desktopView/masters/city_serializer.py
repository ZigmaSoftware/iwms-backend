from rest_framework import serializers
from api.apps.city import City

class CitySerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    state_name = serializers.CharField(source='state.name', read_only=True)
    district_name = serializers.CharField(source='district.name', read_only=True)

    class Meta:
        model = City
        fields = '__all__'

    def validate(self, attrs):
        district = attrs.get("district")
        name = attrs.get("name")
        instance = getattr(self, "instance", None)
        qs = City.objects.filter(district=district, name__iexact=name.strip(), is_deleted=False)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError({"name": "City name already exists for the selected district."})
        return attrs
