from rest_framework import serializers
from app.models.grivences.complaints import Complaint


class ComplaintSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    zone_name = serializers.SerializerMethodField()
    ward_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()
    main_category = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    sub_category = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    image_url = serializers.SerializerMethodField()
    close_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = "__all__"

    def get_customer_name(self, obj):
        return getattr(obj.customer, "customer_name", None)

    def get_zone_name(self, obj):
        return getattr(obj.zone, "zone_name", None)

    def get_ward_name(self, obj):
        return getattr(obj.ward, "ward_name", None)

    def get_company_name(self, obj):
        return getattr(obj.company, "name", None)

    def get_project_name(self, obj):
        return getattr(obj.project, "name", None)

    def get_image_url(self, obj):
        request = self.context.get("request")
        if obj.image:
            return request.build_absolute_uri(obj.image.url)
        return None

    def get_close_image_url(self, obj):
        request = self.context.get("request")
        if obj.close_image:
            return request.build_absolute_uri(obj.close_image.url)
        return None
