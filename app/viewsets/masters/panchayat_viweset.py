from rest_framework import viewsets, status
from app.models.masters.panchayat import Panchayat
from app.serializers.masters.panchayat_serializer import PanchayatSerializer
from rest_framework.response import Response
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.audit_mixin import AuditViewSetMixin


class PanhayatViewSet(AuditViewSetMixin,CompanyScopedViewSet):
    serializer_class = PanchayatSerializer
    lookup_field = "unique_id"
    permission_resource = "Panchayat"

    AUDIT_MODULE = "bp-palakkad"
    AUDIT_ENDPOINT ="panchayat"

    def get_queryset(self):
        return Panchayat.objects.filter(is_deleted=False)

    def perform_destroy(self, instance):
        instance.delete()
