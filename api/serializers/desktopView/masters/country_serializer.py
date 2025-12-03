from rest_framework import serializers
from api.apps.country import Country


class CountrySerializer(serializers.ModelSerializer):
    continent_name = serializers.CharField(
        source="continent_id.name",
        read_only=True
    )

    class Meta:
        model = Country
        fields = "__all__"
        read_only_fields = ["unique_id"]
