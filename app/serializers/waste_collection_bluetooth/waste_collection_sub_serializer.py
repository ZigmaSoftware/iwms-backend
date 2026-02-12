from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.user_creations.waste_collection_bluetooth import WasteCollectionSub


class WasteCollectionSubSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = WasteCollectionSub
        exclude = ["id"]
        read_only_fields = ["date_time"]
