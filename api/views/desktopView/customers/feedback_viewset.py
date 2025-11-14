from rest_framework import viewsets
from api.apps.feedback import FeedBack
from api.serializers.desktopView.customers.feedback_serializer import FeedBackSerializer

class FeedBackViewSet(viewsets.ModelViewSet):
    queryset = FeedBack.objects.filter(is_deleted=False).select_related(
        "customer__ward","customer__zone","customer__city",
        "customer__district","customer__state","customer__country",
        "customer__property","customer__sub_property"
    )
    serializer_class = FeedBackSerializer
