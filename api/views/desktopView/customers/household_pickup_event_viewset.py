from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status

from api.apps.household_pickup_event import HouseholdPickupEvent
from api.serializers.desktopView.customers.household_pickup_event_serializer import (
    HouseholdPickupEventSerializer
)


class HouseholdPickupEventViewSet(ModelViewSet):
    """
    Household-level pickup events.
    Used by operations, reporting, and billing.
    """

    queryset = HouseholdPickupEvent.objects.select_related(
        "customer",
        "zone",
        "property",
        "sub_property",
        "collector_staff",
        "vehicle",
    )
    serializer_class = HouseholdPickupEventSerializer

    swagger_tags = ["Desktop / Customers / Pickup"]
    permission_resource = "HouseholdPickupEvent"

    http_method_names = ["get", "post"]

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Deletion of pickup events is not allowed"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def update(self, request, *args, **kwargs):
        return Response(
            {"detail": "Pickup events are immutable"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
