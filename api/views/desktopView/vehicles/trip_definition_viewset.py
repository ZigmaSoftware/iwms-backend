from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status

from api.apps.trip_definition import TripDefinition
from api.serializers.desktopView.vehicles.trip_definition_serializer import (
    TripDefinitionSerializer
)


class TripDefinitionViewSet(ModelViewSet):
    """
    Trip definition master.
    Used to decide WHEN trips should be instantiated.
    """

    queryset = TripDefinition.objects.select_related(
        "routeplan",
        "staff_template",
        "property",
        "sub_property",
    )

    serializer_class = TripDefinitionSerializer
    swagger_tags = ["Desktop / Operations / Trip Definition"]
    permission_resource = "TripDefinition"

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Trip definitions cannot be deleted"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.approval_status == "APPROVED":
            return Response(
                {"detail": "Approved trip definitions cannot be modified"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().update(request, *args, **kwargs)
