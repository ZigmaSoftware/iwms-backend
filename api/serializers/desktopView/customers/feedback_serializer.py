from rest_framework import serializers
from api.apps.feedback import FeedBack

class FeedBackSerializer(serializers.ModelSerializer):
    customer_id = serializers.CharField(source="customer.unique_id", read_only=True)
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    ward_name = serializers.CharField(source="customer.ward.ward_name", read_only=True)
    zone_name = serializers.CharField(source="customer.zone.name", read_only=True)
    city_name = serializers.CharField(source="customer.city.name", read_only=True)

    class Meta:
        model = FeedBack
        fields = "__all__"
