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
        "customer_id",
        "zone_id",
        "property_id",
        "sub_property_id",
        "collector_staff_id",
        "vehicle_id",
    )
    serializer_class = HouseholdPickupEventSerializer

    swagger_tags = ["Desktop / Customers / Pickup"]
    permission_resource = "HouseholdPickupEvent"

    http_method_names = ["get", "post", "patch", "put"]

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Deletion of pickup events is not allowed"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
