from rest_framework import viewsets
from api.views.tenant_viewset import TenantModelViewSet
from api.apps.customercreation import CustomerCreation
from api.serializers.desktopView.customers.customercreation_serializer import CustomerCreationSerializer

class CustomerCreationViewSet(TenantModelViewSet):
    queryset = CustomerCreation.objects.filter(is_deleted=False).select_related(
        "ward","zone","city","district","state","country","property","sub_property"
    ).order_by("customer_name")
    serializer_class = CustomerCreationSerializer
    lookup_field = "unique_id"
    
