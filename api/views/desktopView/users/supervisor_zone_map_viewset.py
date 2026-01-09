from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

from api.apps.supervisor_zone_map import SupervisorZoneMap
from api.apps.supervisor_zone_access_audit import SupervisorZoneAccessAudit
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
        user = getattr(request, "user", None)
        if not user or not getattr(user, "staffusertype_id", None):
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if user.staffusertype_id.name.lower() != "admin":
            return Response(
                {"detail": "Only admin can update supervisor zone mappings."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        supervisor = serializer.validated_data["supervisor"]
        new_zone_ids = serializer.validated_data["zone_ids"]
        remarks = request.data.get("remarks")

        with transaction.atomic():
            # Deactivate existing ACTIVE mapping
            existing = SupervisorZoneMap.objects.filter(
                supervisor=supervisor,
                status="ACTIVE"
            ).select_for_update().first()

            old_zone_ids = existing.zone_ids if existing else None

            if existing:
                existing.status = "INACTIVE"
                existing.save(update_fields=["status"])

            instance = serializer.save()

            SupervisorZoneAccessAudit.objects.create(
                supervisor=supervisor,
                old_zone_ids=old_zone_ids,
                new_zone_ids=new_zone_ids,
                performed_by=user,
                performed_role="ADMIN",
                remarks=remarks if isinstance(remarks, str) else None,
            )

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
