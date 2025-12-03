from rest_framework import serializers
from api.apps.continent import Continent

class ContinentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Continent
        fields = '__all__'
        read_only_fields = ["unique_id"]
