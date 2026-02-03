from rest_framework import viewsets
from api.views.tenant_viewset import TenantModelViewSet
from api.apps.feedback import FeedBack
from api.serializers.desktopView.customers.feedback_serializer import FeedBackSerializer

class FeedBackViewSet(TenantModelViewSet):
    queryset = FeedBack.objects.filter(is_deleted=False).select_related(
        "customer__ward","customer__zone","customer__city",
        "customer__district","customer__state","customer__country",
        "customer__property_ref","customer__sub_property"
    )
    serializer_class = FeedBackSerializer
    lookup_field = "unique_id"
