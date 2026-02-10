from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.serializers.waste_collection_bluetooth.waste_type_serializer import (
    WasteTypeSerializer,
)


class WasteTypeViewSet(CompanyScopedViewSet):
    queryset = WasteType.objects.filter(is_deleted=False)
    serializer_class = WasteTypeSerializer
    permission_resource = "WasteType"

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted"])
