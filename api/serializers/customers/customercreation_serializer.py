from rest_framework import serializers
from ...apps.customercreation import CustomerCreation

class CustomerCreationSerializer(serializers.ModelSerializer):
    ward_name = serializers.CharField(source="ward.name", read_only=True)
    zone_name = serializers.CharField(source="zone.name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)
    district_name = serializers.CharField(source="district.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    country_name = serializers.CharField(source="country.name", read_only=True)
    property_name = serializers.CharField(source="property.property_name", read_only=True)
    sub_property_name = serializers.CharField(source="sub_property.sub_property_name", read_only=True)

    class Meta:
        model = CustomerCreation
        fields = "__all__"
