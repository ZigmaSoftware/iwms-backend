from rest_framework import serializers
from ...apps.wastecollection import WasteCollection

class WasteCollectionSerializer(serializers.ModelSerializer):
    ward_name = serializers.CharField(source="customer.ward.ward_name", read_only=True)
    zone_name = serializers.CharField(source="customer.zone.name", read_only=True, default=None)
    city_name = serializers.CharField(source="customer.city.name", read_only=True)
    district_name = serializers.CharField(source="customer.district.name", read_only=True)
    state_name = serializers.CharField(source="customer.state.name", read_only=True)
    country_name = serializers.CharField(source="customer.country.name", read_only=True)
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)

    class Meta:
        model = WasteCollection
        fields = "__all__"
