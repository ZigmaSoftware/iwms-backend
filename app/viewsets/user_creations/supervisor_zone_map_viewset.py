from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.user_creations.supervisor_zone_map import SupervisorZoneMap
from app.models.user_creations.staffcreation import Staffcreation
from app.serializers.user_creations.supervisor_zone_map_serializer import (
    SupervisorZoneMapSerializer,
)
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.audit_mixin import AuditViewSetMixin


class SupervisorZoneMapViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    """
    CRUD for supervisor → zone authorization maps.

    A supervisor sees only their own zone maps; admins/superadmins see all
    (subject to company scoping). Custom action:
      GET /supervisor-zone-map/me/  — the current supervisor's active zone scope
    """

    queryset = SupervisorZoneMap.objects.select_related(
        "supervisor_id",
        "district_id",
        "city_id",
    ).filter(is_deleted=False)

    serializer_class = SupervisorZoneMapSerializer
    lookup_field = "unique_id"
    permission_resource = "SupervisorZoneMap"
    swagger_tags = ["Desktop / Supervisor Zones"]

    AUDIT_MODULE = "user-creations"
    AUDIT_ENDPOINT = "supervisor-zone-map"

    # ----------------------------------------------------------
    # QUERYSET — scope supervisors to their own maps
    # ----------------------------------------------------------

    def get_queryset(self):
        qs = super().get_queryset()

        params = self.request.query_params
        status_param = params.get("status")
        district = params.get("district_id")
        city = params.get("city_id")

        if status_param:
            qs = qs.filter(status=status_param)
        if district:
            qs = qs.filter(district_id=district)
        if city:
            qs = qs.filter(city_id=city)

        # A plain supervisor only sees the maps they own.
        staff_id = self._current_staff_unique_id()
        if staff_id and self._is_supervisor() and not self._has_admin_role():
            qs = qs.filter(supervisor_id=staff_id)

        return qs

    # ----------------------------------------------------------
    # ACTION: GET /supervisor-zone-map/me/
    # ----------------------------------------------------------

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        """Return the requesting supervisor's active zone maps."""
        staff_id = self._current_staff_unique_id()
        if not staff_id:
            return Response(
                {"detail": "No supervisor staff context for the current user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = self.filter_queryset(self.get_queryset()).filter(
            supervisor_id=staff_id,
            status=SupervisorZoneMap.STATUS_ACTIVE,
        )
        serializer = self.get_serializer(qs, many=True)

        zone_ids = []
        for entry in qs:
            zone_ids.extend(entry.zone_ids or [])

        return Response(
            {
                "supervisor_id": staff_id,
                "zone_ids": sorted(set(zone_ids)),
                "maps": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    # ----------------------------------------------------------
    # HELPERS
    # ----------------------------------------------------------

    def _current_staff_unique_id(self):
        user = getattr(self.request, "user", None)
        if isinstance(user, Staffcreation):
            return user.staff_unique_id
        return getattr(user, "staff_unique_id", None)

    def _role_name(self):
        user = getattr(self.request, "user", None)
        role_obj = getattr(user, "staffusertype_id", None)
        return (getattr(role_obj, "name", "") or "").lower()

    def _is_supervisor(self):
        return "supervisor" in self._role_name()

    def _has_admin_role(self):
        if self._is_platform_super_admin():
            return True
        return self._role_name() in ("admin", "company_admin")
