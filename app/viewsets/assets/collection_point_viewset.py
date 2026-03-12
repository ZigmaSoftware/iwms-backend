from rest_framework import viewsets, status
from app.models.assets.collection_point import Collection_point
from app.serializers.assets.collection_point_serializer import CollectionPointSerializer
from rest_framework.response import Response
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.audit_mixin import AuditViewSetMixin


class CollectionPointViewSet(AuditViewSetMixin,CompanyScopedViewSet):
    serializer_class = CollectionPointSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "bp-palakkad"
    AUDIT_ENDPOINT ="collection-point"

    def get_queryset(self):
        return Collection_point.objects.filter(is_deleted=False)

    def perform_destroy(self, instance):
        instance.delete()