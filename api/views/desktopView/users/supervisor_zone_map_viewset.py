from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

from api.apps.supervisor_zone_map import SupervisorZoneMap
from api.serializers.desktopView.users.supervisor_zone_map_serializer import (
    SupervisorZoneMapSerializer
)


class SupervisorZoneMapViewSet(ModelViewSet):
    """
    Zone assignment controller.
    Authorization enforced via JWT + ModulePermissionMiddleware.
    """

    queryset = SupervisorZoneMap.objects.all()
    serializer_class = SupervisorZoneMapSerializer

    # IMPORTANT for middleware permission resolution
    permission_resource = "SupervisorZoneMap"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        supervisor = serializer.validated_data["supervisor"]

        with transaction.atomic():
            # Deactivate existing ACTIVE mapping
            SupervisorZoneMap.objects.filter(
                supervisor=supervisor,
                status="ACTIVE"
            ).update(status="INACTIVE")

            instance = serializer.save()

        return Response(
            SupervisorZoneMapSerializer(instance).data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        return Response(
            {
                "detail": "Direct update is not allowed. "
                          "Deactivate and create a new zone assignment."
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {
                "detail": "Deletion is not allowed for zone assignments."
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
