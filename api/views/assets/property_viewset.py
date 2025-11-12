from rest_framework import viewsets
from ...apps.property import Property
from ...serializers.assets.property_serializer import PropertySerializer

class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.filter(is_deleted=False)
    serializer_class = PropertySerializer
