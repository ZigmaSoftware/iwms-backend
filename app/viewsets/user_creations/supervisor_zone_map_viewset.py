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



class SupervisorZoneMapViewSet(CompanyScopedViewSet,AuditViewSetMixin):
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
        user = request.user

        if not user or user.is_anonymous:
            raise NotAuthenticated("Authentication required.")
        
        allowed_roles = ["company admin", "superadmin"]

        if user.staffusertype_id.name.lower() not in allowed_roles:
            return Response(
                {"detail": "Only company admin or superadmin can update supervisor zone mappings."},
                status=status.HTTP_403_FORBIDDEN,
            )

        instance = self.get_object()
        old_zone_ids = instance.zone_ids

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        updated_instance = serializer.save(
            company_id=getattr(instance, "company_id", None) or getattr(user, "company_id", None),
            project_id=getattr(instance, "project_id", None) or getattr(user, "project_id", None),
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



# from rest_framework.viewsets import ModelViewSet
# from rest_framework.response import Response
# from rest_framework import status
# from django.db import transaction
# from rest_framework.exceptions import NotAuthenticated

# from app.models.user_creations.supervisor_zone_map import SupervisorZoneMap
# from app.models.audits.supervisor_zone_access_audit import SupervisorZoneAccessAudit
# from app.serializers.user_creations.supervisor_zone_map_serializer import SupervisorZoneMapSerializer
# from app.models.user_creations.staffcreation import Staffcreation
# # from app.models.user_creations.staffcreation_office_details import StaffcreationOfficeDetails


# class SupervisorZoneMapViewSet(ModelViewSet):
#     queryset = SupervisorZoneMap.objects.all()
#     serializer_class = SupervisorZoneMapSerializer
#     lookup_field = "unique_id"

#     permission_resource = "supervisor-zone-map"

#     # ============================================================
#     # RESOLVE USER (SAME AS STAFF TEMPLATE)
#     # ============================================================
#     def _resolve_request_user(self):
#         user = getattr(self.request, "user", None)

#         if user and not getattr(user, "is_anonymous", False):
#             if isinstance(user, Staffcreation) or hasattr(user, "staff_unique_id"):
#                 return user

#             staff = getattr(user, "staff", None)
#             if staff:
#                 return staff

#         # Try from jwt_payload set by authentication backend
#         payload = getattr(self.request, "jwt_payload", None)
#         if isinstance(payload, dict):
#             unique_id = payload.get("unique_id")
#             if unique_id:
#                 return Staffcreation.objects.filter(
#                     staff_unique_id=unique_id
#                 ).first()

#         return None

#     # ============================================================
#     # GET OFFICE USER (IMPORTANT FIX)
#     # ============================================================
#     def _get_office_user(self, staff_user):
#         if not staff_user:
#             return None

#         return Staffcreation.objects.filter(
#             staff_id=staff_user
#         ).first()

#     # ============================================================
#     # ROLE CHECK
#     # ============================================================
#     def _is_admin_user(self):
#         """
#         Check if the authenticated user is superadmin or company admin.
#         Extracts role from the staff user's staffusertype_id.name attribute.
#         """
#         user = self._resolve_request_user()
        
#         if not user:
#             return False
        
#         # Get the staff user type name
#         staff_user_type = getattr(user, "staffusertype_id", None)
#         if not staff_user_type:
#             return False
        
#         role = getattr(staff_user_type, "name", "").lower().strip()
#         return role in ["superadmin", "company admin"]

#     # ============================================================
#     # CREATE
#     # ============================================================
#     def create(self, request, *args, **kwargs):

#         if not self._is_admin_user():
#             return Response(
#                 {"detail": "Only company admin or superadmin can create supervisor zone mappings."},
#                 status=status.HTTP_403_FORBIDDEN,
#             )

#         staff_user = self._resolve_request_user()
#         office_user = self._get_office_user(staff_user)

#         if not office_user:
#             raise NotAuthenticated("Valid staff office user not found")

#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         supervisor = serializer.validated_data["supervisor_id"]
#         new_zone_ids = serializer.validated_data["zone_ids"]
#         remarks = request.data.get("remarks")

#         company = getattr(supervisor, "company_id", None) or getattr(staff_user, "company_id", None)
#         project = getattr(supervisor, "project_id", None) or getattr(staff_user, "project_id", None)

#         with transaction.atomic():
#             existing = SupervisorZoneMap.objects.filter(
#                 supervisor_id=supervisor,
#                 status="ACTIVE"
#             ).select_for_update().first()

#             old_zone_ids = existing.zone_ids if existing else None

#             if existing:
#                 existing.status = "INACTIVE"
#                 existing.save(update_fields=["status"])

#             instance = serializer.save(
#                 company_id=company,
#                 project_id=project,
#             )

#             SupervisorZoneAccessAudit.objects.create(
#                 supervisor=supervisor,
#                 old_zone_ids=old_zone_ids,
#                 new_zone_ids=new_zone_ids,
#                 performed_by=office_user,   # ✅ FIXED
#                 performed_role="ADMIN",
#                 remarks=remarks if isinstance(remarks, str) else None,
#                 company_id=company,
#                 project_id=project,
#             )

#         return Response(
#             SupervisorZoneMapSerializer(instance).data,
#             status=status.HTTP_201_CREATED
#         )

#     # ============================================================
#     # UPDATE
#     # ============================================================
#     def update(self, request, *args, **kwargs):

#         if not self._is_admin_user():
#             return Response(
#                 {"detail": "Only company admin or superadmin can update supervisor zone mappings."},
#                 status=status.HTTP_403_FORBIDDEN,
#             )

#         staff_user = self._resolve_request_user()
#         office_user = self._get_office_user(staff_user)

#         if not office_user:
#             raise NotAuthenticated("Valid staff office user not found")

#         instance = self.get_object()
#         old_zone_ids = instance.zone_ids

#         serializer = self.get_serializer(instance, data=request.data, partial=True)
#         serializer.is_valid(raise_exception=True)

#         updated_instance = serializer.save(
#             company_id=getattr(instance, "company_id", None) or getattr(staff_user, "company_id", None),
#             project_id=getattr(instance, "project_id", None) or getattr(staff_user, "project_id", None),
#         )

#         new_zone_ids = updated_instance.zone_ids
#         remarks = request.data.get("remarks")

#         SupervisorZoneAccessAudit.objects.create(
#             supervisor=updated_instance.supervisor_id,
#             old_zone_ids=old_zone_ids,
#             new_zone_ids=new_zone_ids,
#             performed_by=office_user,   # ✅ FIXED
#             performed_role="ADMIN",
#             remarks=remarks if isinstance(remarks, str) else None,
#             company_id=getattr(updated_instance, "company_id", None) or getattr(staff_user, "company_id", None),
#             project_id=getattr(updated_instance, "project_id", None) or getattr(staff_user, "project_id", None),
#         )

#         return Response(
#             SupervisorZoneMapSerializer(updated_instance).data,
#             status=status.HTTP_200_OK,
#         )

#     # ============================================================
#     # DESTROY (DELETE)
#     # ============================================================
#     def destroy(self, request, *args, **kwargs):
#         """
#         Deletion is not allowed for zone assignments.
#         Deactivate instead by using update with status='INACTIVE'.
#         """
#         return Response(
#             {
#                 "detail": "Deletion is not allowed for zone assignments. Use update to set status='INACTIVE'."
#             },
#             status=status.HTTP_405_METHOD_NOT_ALLOWED
#         )

#     # ============================================================
#     # LIST
#     # ============================================================
#     def list(self, request, *args, **kwargs):
#         """
#         List all supervisor zone mappings.
#         Only superadmin and company admin can view.
#         """
#         if not self._is_admin_user():
#             return Response(
#                 {"detail": "Only company admin or superadmin can view supervisor zone mappings."},
#                 status=status.HTTP_403_FORBIDDEN,
#             )

#         return super().list(request, *args, **kwargs)

#     # ============================================================
#     # RETRIEVE
#     # ============================================================
#     def retrieve(self, request, *args, **kwargs):
#         """
#         Retrieve a specific supervisor zone mapping.
#         Only superadmin and company admin can view.
#         """
#         if not self._is_admin_user():
#             return Response(
#                 {"detail": "Only company admin or superadmin can view supervisor zone mappings."},
#                 status=status.HTTP_403_FORBIDDEN,
#             )

#         return super().retrieve(request, *args, **kwargs)