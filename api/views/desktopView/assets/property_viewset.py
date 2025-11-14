from rest_framework import viewsets
from api.apps.property import Property
from api.serializers.desktopView.assets.property_serializer import PropertySerializer

class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.filter(is_deleted=False)
    serializer_class = PropertySerializer
