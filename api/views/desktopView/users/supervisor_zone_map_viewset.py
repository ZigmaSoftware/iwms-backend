from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from django.db import transaction

from api.apps.supervisor_zone_map import SupervisorZoneMap
from api.apps.supervisor_zone_access_audit import SupervisorZoneAccessAudit
from api.apps.userCreation import User
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

    def _resolve_request_user(self):
        user = getattr(self.request, "user", None)
        if user and not getattr(user, "is_anonymous", False):
            return user

        raw_request = getattr(self.request, "_request", None)
        raw_user = getattr(raw_request, "user", None) if raw_request else None
        if raw_user and not getattr(raw_user, "is_anonymous", False):
            return raw_user

        payload = getattr(self.request, "jwt_payload", None) or getattr(raw_request, "jwt_payload", None)
        unique_id = payload.get("unique_id") if isinstance(payload, dict) else None
        if unique_id:
            return User.objects.filter(unique_id=unique_id).first()

        return None

    def create(self, request, *args, **kwargs):
        user = self._resolve_request_user()
        if not user or not getattr(user, "staffusertype_id", None):
            raise NotAuthenticated("Authentication required.")

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
        user = self._resolve_request_user()
        if not user or not getattr(user, "staffusertype_id", None):
            raise NotAuthenticated("Authentication required.")

        if user.staffusertype_id.name.lower() != "admin":
            return Response(
                {"detail": "Only admin can update supervisor zone mappings."},
                status=status.HTTP_403_FORBIDDEN,
            )

        instance = self.get_object()
        old_zone_ids = instance.zone_ids

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        updated_instance = serializer.save()
        new_zone_ids = updated_instance.zone_ids
        remarks = request.data.get("remarks")

        SupervisorZoneAccessAudit.objects.create(
            supervisor=updated_instance.supervisor,
            old_zone_ids=old_zone_ids,
            new_zone_ids=new_zone_ids,
            performed_by=user,
            performed_role="ADMIN",
            remarks=remarks if isinstance(remarks, str) else None,
        )

        return Response(
            SupervisorZoneMapSerializer(updated_instance).data,
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {
                "detail": "Deletion is not allowed for zone assignments."
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
