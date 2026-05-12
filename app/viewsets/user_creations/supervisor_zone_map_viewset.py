from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from django.db import transaction

from app.models.user_creations.supervisor_zone_map import SupervisorZoneMap
from app.models.audits.supervisor_zone_access_audit import SupervisorZoneAccessAudit
from app.models.user_creations.staffcreation import Staffcreation
from app.serializers.user_creations.supervisor_zone_map_serializer import (
    SupervisorZoneMapSerializer
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet



class SupervisorZoneMapViewSet(AuditViewSetMixin,CompanyScopedViewSet):
    """
    Zone assignment controller.
    Authorization enforced via JWT + ModulePermissionMiddleware.
    """

    queryset = SupervisorZoneMap.objects.all()
    serializer_class = SupervisorZoneMapSerializer
    lookup_field = "unique_id"
    # IMPORTANT for middleware permission resolution
    permission_resource = "SupervisorZoneMap"

    AUDIT_MODULE = "user_creations"
    AUDIT_ENDPOINT = "supervisor-zone-map"
   
    def _resolve_request_user(self):
        user = self.request.user
        if user and not user.is_anonymous:
            return user

        payload = getattr(self.request, "jwt_payload", None)
        if payload:
            unique_id = payload.get("unique_id")
            if unique_id:
                return Staffcreation.objects.filter(
                    staff_unique_id=unique_id
                ).first()

        return None
    

    def create(self, request, *args, **kwargs):
        user = self._resolve_request_user()

        if not user or user.is_anonymous:
            raise NotAuthenticated("Authentication required.")

        # ✅ Allow superadmin directly
        if getattr(user, "is_superuser", False) or getattr(user, "is_superadmin", False):
            pass  # full access

        else:
            # ✅ Then check company admin role
            if not user.staffusertype_id or not user.staffusertype_id.name:
                return Response(
                    {"detail": "User role not assigned properly."},
                    status=status.HTTP_403_FORBIDDEN
                )

            if user.staffusertype_id.name.lower() != "company admin":
                return Response(
                    {"detail": "Only company admin or superadmin allowed."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        supervisor = serializer.validated_data["supervisor_id"]
        new_zone_ids = serializer.validated_data["zone_ids"]
        remarks = request.data.get("remarks")
        company = getattr(supervisor, "company_id", None) or getattr(user, "company_id", None)
        project = getattr(supervisor, "project_id", None) or getattr(user, "project_id", None)

        with transaction.atomic():
            # Deactivate existing ACTIVE mapping
            existing = SupervisorZoneMap.objects.filter(
                supervisor_id=supervisor,
                status="ACTIVE"
            ).select_for_update().first()

            old_zone_ids = existing.zone_ids if existing else None

            if existing:
                existing.status = "INACTIVE"
                existing.save(update_fields=["status"])

            instance = serializer.save(
                company_id=company,
                project_id=project,
            )

            new_data = self._serialize_instance(instance)

            self.log_audit(
                self.request,
                instance=instance,
                previous_data=None,
                new_data=new_data
            )

            SupervisorZoneAccessAudit.objects.create(
                supervisor=supervisor,
                old_zone_ids=old_zone_ids,
                new_zone_ids=new_zone_ids,
                # performed_by=user,
                performed_role="ADMIN",
                remarks=remarks if isinstance(remarks, str) else None,
                company_id=company,
                project_id=project,
            )

        return Response(
            SupervisorZoneMapSerializer(instance).data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        user = self._resolve_request_user()

        if not user or user.is_anonymous:
            raise NotAuthenticated("Authentication required.")

        allowed_roles = ["company admin", "superadmin"]

        # ✅ direct superadmin access
        if getattr(user, "is_superuser", False) or getattr(user, "is_superadmin", False):
            pass

        else:
            if not getattr(user, "staffusertype_id", None):
                return Response(
                    {"detail": "User role not assigned properly."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            role_name = getattr(user.staffusertype_id, "name", "").lower()

            if role_name not in allowed_roles:
                return Response(
                    {
                        "detail": "Only company admin or superadmin can update supervisor zone mappings."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        instance = self.get_object()
        previous_data = self._serialize_instance(instance)
        old_zone_ids = instance.zone_ids

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        updated_instance = serializer.save(
            company_id=getattr(instance, "company_id", None) or getattr(user, "company_id", None),
            project_id=getattr(instance, "project_id", None) or getattr(user, "project_id", None),
        )

        new_data = self._serialize_instance(updated_instance)

        self.log_audit(
            self.request,
            instance=updated_instance,
            previous_data=previous_data,
            new_data=new_data
        )


        new_zone_ids = updated_instance.zone_ids
        remarks = request.data.get("remarks")

        SupervisorZoneAccessAudit.objects.create(
            supervisor=updated_instance.supervisor_id,
            old_zone_ids=old_zone_ids,
            new_zone_ids=new_zone_ids,
            # performed_by=user,
            performed_role="ADMIN",
            remarks=remarks if isinstance(remarks, str) else None,
            company_id=getattr(updated_instance, "company_id", None) or getattr(user, "company_id", None),
            project_id=getattr(updated_instance, "project_id", None) or getattr(user, "project_id", None),
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
