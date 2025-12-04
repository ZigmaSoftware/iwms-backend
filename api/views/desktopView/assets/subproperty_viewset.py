from rest_framework import viewsets
from api.apps.subproperty import SubProperty
from api.serializers.desktopView.assets.subproperty_serializer import SubPropertySerializer

class SubPropertyViewSet(viewsets.ModelViewSet):
    queryset = SubProperty.objects.filter(is_deleted=False)\
        .select_related("property_id")\
        .order_by("sub_property_name")

    serializer_class = SubPropertySerializer
    lookup_field = "unique_id"

    def perform_destroy(self, instance):
        instance.delete()
