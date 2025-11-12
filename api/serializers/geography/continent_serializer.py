from rest_framework import serializers
from ...apps.continent import Continent

class ContinentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Continent
        fields = '__all__'
