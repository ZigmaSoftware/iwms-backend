from rest_framework.viewsets import ModelViewSet
from app.models.transport_masters.trip import Trip
from app.serializers.transport_masters.trip_serializer import TripSerializer
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.audit_mixin import AuditViewSetMixin


class TripViewSet(AuditViewSetMixin,CompanyScopedViewSet):

    serializer_class = TripSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "bp-palakkad"
    AUDIT_ENDPOINT ="trip"

    def get_queryset(self):
        return Trip.objects.filter( 
            is_deleted=False
        )

    def perform_destroy(self, instance):
        instance.delete()