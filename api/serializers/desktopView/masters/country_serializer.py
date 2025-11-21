from rest_framework import serializers
from api.apps.country import Country

class CountrySerializer(serializers.ModelSerializer):
    continent_name = serializers.CharField(source='continent.name', read_only=True)

    class Meta:
        model = Country
        fields = '__all__'
