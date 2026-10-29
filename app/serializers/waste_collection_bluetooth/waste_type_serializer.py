from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.utils.related_prefetch import prefetching_list_serializer, related

RELATED_LOOKUPS = {
    "company": (Company, "company_id"),
    "project": (Project, "project_id"),
}


class WasteTypeSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = WasteType
        fields = "__all__"
        list_serializer_class = prefetching_list_serializer(RELATED_LOOKUPS)

    def get_company_name(self, obj):
        return getattr(related(obj, "company"), "name", None)

    def get_project_name(self, obj):
        return getattr(related(obj, "project"), "name", None)
