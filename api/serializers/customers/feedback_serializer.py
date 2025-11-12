from rest_framework import serializers
from ...apps.feedback import FeedBack

class FeedBackSerializer(serializers.ModelSerializer):
    ward_name = serializers.CharField(source="customer.ward.ward_name", read_only=True)
    zone_name = serializers.CharField(source="customer.zone.name", read_only=True, default=None)
    city_name = serializers.CharField(source="customer.city.name", read_only=True)

    class Meta:
        model = FeedBack
        fields = "__all__"
