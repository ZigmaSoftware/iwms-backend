from app.utils.audit_mixin import DeleteReasonMixin
from app.viewsets.superadmin_masters.company_scoped_viewset import CompanyScopedViewSet
from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteCollectionMain
from app.serializers.waste_collection_bluetooth.waste_collection_main_serializer import (
    WasteCollectionMainSerializer,
)


class WasteCollectionMainViewSet(DeleteReasonMixin, CompanyScopedViewSet):
    queryset = WasteCollectionMain.objects.filter(is_deleted=False)
    serializer_class = WasteCollectionMainSerializer
    lookup_field = "unique_id"
    permission_resource = "WasteCollectionMain"
    AUDIT_MODULE = "waste-collection"
    AUDIT_ENDPOINT = "waste-collection-main"

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted"])
