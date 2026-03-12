# app/api/views/area_type_view.py

from rest_framework.viewsets import ModelViewSet
from app.models.masters.areatype import AreaType
from app.serializers.masters.areatype_serializer import AreaTypeSerializer
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.audit_mixin import AuditViewSetMixin


class AreaTypeViewSet(AuditViewSetMixin,CompanyScopedViewSet):
    
    serializer_class = AreaTypeSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "bp-palakkad"
    AUDIT_ENDPOINT ="areatype"


    def get_queryset(self):
        return AreaType.objects.filter(is_deleted=False)

    def perform_destroy(self, instance):
        instance.delete()