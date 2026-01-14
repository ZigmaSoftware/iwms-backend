from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

from api.apps.vehicle_trip_audit import VehicleTripAudit
from api.serializers.desktopView.vehicles.vehicle_trip_audit_serializer import (
    VehicleTripAuditSerializer
)


class VehicleTripAuditViewSet(ModelViewSet):
    """
    GPS audit ingestion for trip replay & idle analysis.
    Triggered automatically every N seconds by vehicle/mobile.
    """

    queryset = VehicleTripAudit.objects.all()
    serializer_class = VehicleTripAuditSerializer
    permission_resource = "VehicleTripAudit"
    swagger_tags = ["Desktop / Vehicle Trip Audit"]

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data["captured_at"] = timezone.now()

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        instance = serializer.save()

        return Response(
            VehicleTripAuditSerializer(instance).data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        immutable_fields = {"trip_instance_id", "vehicle_id", "captured_at"}
        if immutable_fields.intersection(request.data.keys()):
            return Response(
                {"detail": "Trip, vehicle, and captured_at cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Vehicle audit records cannot be deleted"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
