from rest_framework import serializers
from ...apps.complaints import Complaint

class ComplaintSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    zone_name = serializers.CharField(source="zone.name", read_only=True)
    ward_name = serializers.CharField(source="ward.name", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = "__all__"

    def get_image_url(self, obj):
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, "url"):
            return request.build_absolute_uri(obj.image.url)
        return None
