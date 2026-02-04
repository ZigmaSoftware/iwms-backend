from rest_framework import viewsets
from app.viewsets.superadminmasters.tenant_viewset import TenantModelViewSet
from app.models.customers.customercreation import CustomerCreation
from app.serializers.desktop.customers.customercreation_serializer import CustomerCreationSerializer

class CustomerCreationViewSet(TenantModelViewSet):
    queryset = CustomerCreation.objects.filter(is_deleted=False).select_related(
        "ward","zone","city","district","state","country","property_ref","sub_property"
    ).order_by("customer_name")
    serializer_class = CustomerCreationSerializer
    lookup_field = "unique_id"
    
