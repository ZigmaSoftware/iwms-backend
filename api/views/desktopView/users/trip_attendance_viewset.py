from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from django.utils import timezone

from api.apps.trip_attendance import TripAttendance
from api.apps.trip_instance import TripInstance
from api.serializers.desktopView.users.trip_attendance_serializer import (
    TripAttendanceSerializer
)


class TripAttendanceViewSet(ModelViewSet):
    """
    Mobile-triggered periodic attendance capture.
    Invoked every 45 minutes per staff during a trip.
    """

    queryset = TripAttendance.objects.all()
    serializer_class = TripAttendanceSerializer
    permission_resource = "TripAttendance"
    swagger_tags = ["Desktop / Trip Attendance"]

    @staticmethod
    def _resolve_user(request):
        user = getattr(request, "user", None)
        if getattr(user, "unique_id", None):
            return user

        raw_request = getattr(request, "_request", None)
        raw_user = getattr(raw_request, "user", None)
        if getattr(raw_user, "unique_id", None):
            return raw_user

        return None

    def create(self, request, *args, **kwargs):
        user = getattr(request, "user", None)
        if not user or getattr(user, "is_anonymous", False):
            raise NotAuthenticated("Authentication required")
        payload = getattr(request, "jwt_payload", None)
        role = (payload.get("role") or "").lower() if isinstance(payload, dict) else None
        if not role and user:
            staff_type = getattr(user, "staffusertype_id", None)
            role = staff_type.name.lower() if staff_type else None

        data = request.data.copy()
        data["attendance_time"] = timezone.now()

        if data.get("trip_instance_id") and not data.get("vehicle_id"):
            trip = TripInstance.objects.filter(
                unique_id=data["trip_instance_id"]
            ).select_related("vehicle").first()
            if trip and trip.vehicle:
                data["vehicle_id"] = trip.vehicle.unique_id

        if role in {"operator", "driver"}:
            if data.get("staff_id") and data.get("staff_id") != user.unique_id:
                return Response(
                    {"detail": "You can only submit your own attendance."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            data["staff_id"] = user.unique_id

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        instance = serializer.save()

        return Response(
            TripAttendanceSerializer(instance).data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        immutable_fields = {"trip_instance_id", "staff_id", "vehicle_id", "attendance_time"}
        if immutable_fields.intersection(request.data.keys()):
            return Response(
                {"detail": "Trip, staff, vehicle, and attendance_time cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = getattr(request, "user", None)
        if not user or getattr(user, "is_anonymous", False):
            raise NotAuthenticated("Authentication required")
        payload = getattr(request, "jwt_payload", None)
        role = (payload.get("role") or "").lower() if isinstance(payload, dict) else None
        if not role and user:
            staff_type = getattr(user, "staffusertype_id", None)
            role = staff_type.name.lower() if staff_type else None

        if role in {"operator", "driver"}:
            instance = self.get_object()
            if instance.staff_id != user.unique_id:
                return Response(
                    {"detail": "You can only update your own attendance."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        return super().update(request, *args, **kwargs)
