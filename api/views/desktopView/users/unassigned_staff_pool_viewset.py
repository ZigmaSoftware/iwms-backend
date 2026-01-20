from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from api.apps.unassigned_staff_pool import UnassignedStaffPool
from api.serializers.desktopView.users.unassigned_staff_pool_serializer import (
    UnassignedStaffPoolSerializer
)


class UnassignedStaffPoolViewSet(ModelViewSet):
    """
    Controls staff availability by zone & ward.
    Used by system + supervisors.
    """

    serializer_class = UnassignedStaffPoolSerializer
    permission_resource = "UnassignedStaffPool"
    swagger_tags = ["Desktop / Staff Availability"]

    def get_queryset(self):
        qs = UnassignedStaffPool.objects.all()
        status_param = self.request.query_params.get("status")
        if status_param:
            return qs.filter(status=status_param)
        return qs.filter(status=UnassignedStaffPool.Status.AVAILABLE)

    def perform_create(self, serializer):
        self._validate_trip_instance_alignment(serializer.validated_data)
        serializer.save()

    def perform_update(self, serializer):
        self._validate_trip_instance_alignment(serializer.validated_data)
        serializer.save()

    def _validate_trip_instance_alignment(self, attrs):
        trip_instance = attrs.get("trip_instance")
        zone = attrs.get("zone")
        ward = attrs.get("ward")

        if trip_instance and zone and trip_instance.zone_id != zone.unique_id:
            raise ValidationError(
                {"trip_instance_id": "Trip instance zone does not match pool zone."}
            )

        if ward and zone and ward.zone_id_id != zone.unique_id:
            raise ValidationError(
                {"ward_id": "Ward does not belong to the selected zone."}
            )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Deletion is not allowed. Update status instead."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
