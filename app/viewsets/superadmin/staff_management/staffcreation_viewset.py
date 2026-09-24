from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from app.viewsets.superadmin_masters.company_scoped_viewset import CompanyScopedViewSet

from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin.staff_management.department import Department
from app.models.superadmin.role_management.projectStaffHierarchy import ProjectStaffHierarchy
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.permissions.platform import SuperAdminApprovalPermission
from app.serializers.superadmin.staff_management.staffcreation_serializer import (
    StaffApprovalActionSerializer,
    StaffcreationSerializer,
)
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)
from app.utils.pagination import LimitOffsetWithPage


class StaffcreationViewset(AuditViewSetMixin,CompanyScopedViewSet):
    pagination_class = LimitOffsetWithPage
    queryset = Staffcreation.objects.filter(is_deleted=False)
    serializer_class = StaffcreationSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    permission_resource = "StaffCreation"
    lookup_field = "staff_unique_id"

    AUDIT_MODULE = "staff-creations"
    AUDIT_ENDPOINT = "staffcreation"

    filter_backends = [
        ModelFieldQueryFilter,
        ModelFieldSearchFilter,
        SerializerOrderingFilter,
    ]
    search_fields = [
        "staff_id",
        "employee_name",
        "staff_unique_id",
        "site_name",
        "department",
        "designation",
    ]
    ordering_fields = ["staff_id", "staff_unique_id", "employee_name", "created_at"]

    approval_action_names = {"approve", "reject", "suspend", "reactivate"}

    def get_permissions(self):
        if getattr(self, "action", None) in self.approval_action_names:
            return [SuperAdminApprovalPermission()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = Staffcreation.objects.filter(is_deleted=False)

        site_name = self.request.query_params.get("site_name", None)
        employee_name = self.request.query_params.get("employee_name", None)
        active_status = self.request.query_params.get("active_status", None)
        salary_type = self.request.query_params.get("salary_type", None)
        department_id = self.request.query_params.get("department_id", None)
        staffusertype_id = self.request.query_params.get("staffusertype_id", None)
        staff_role = self.request.query_params.get("staff_role", None)
        contractorusertype_id = self.request.query_params.get("contractorusertype_id", None)
        approval_status = self.request.query_params.get("approval_status", None)
        login_enabled = self.request.query_params.get("login_enabled", None)

        if site_name:
            queryset = queryset.filter(site_name__icontains=site_name)

        if employee_name:
            queryset = queryset.filter(employee_name__icontains=employee_name)

        if active_status in ["0", "1"]:
            queryset = queryset.filter(active_status=active_status == "1")

        if salary_type:
            queryset = queryset.filter(salary_type__icontains=salary_type)

        if department_id:
            queryset = queryset.filter(department_id=department_id)

        if staffusertype_id:
            queryset = queryset.filter(staffusertype_id=staffusertype_id)

        if staff_role:
            staff_role_ids = StaffUserType.objects.filter(
                name__iexact=staff_role,
                is_deleted=False,
            ).values_list("unique_id", flat=True)
            queryset = queryset.filter(staffusertype_id__in=staff_role_ids)

        if contractorusertype_id:
            queryset = queryset.filter(contractorusertype_id=contractorusertype_id)

        if approval_status:
            queryset = queryset.filter(approval_status=approval_status.upper())

        if login_enabled in ["0", "1", "true", "false", "True", "False"]:
            queryset = queryset.filter(login_enabled=str(login_enabled).lower() in ["1", "true"])

        if self._is_supervisor_user():
            from app.models.core_modules.schedule_setup.trip_plan import TripPlan
            from app.models.core_modules.schedule_setup.staff_template import StaffTemplate

            supervisor_staff_id = self.request.user.staff_unique_id
            supervised_template_ids = TripPlan.objects.filter(
                supervisor_id=supervisor_staff_id,
            ).exclude(staff_template_id__isnull=True).values_list("staff_template_id", flat=True)
            supervised_staff_ids = set(
                StaffTemplate.objects.filter(unique_id__in=supervised_template_ids)
                .exclude(driver_id__isnull=True)
                .values_list("driver_id", flat=True)
            ) | set(
                StaffTemplate.objects.filter(unique_id__in=supervised_template_ids)
                .exclude(operator_id__isnull=True)
                .values_list("operator_id", flat=True)
            )
            queryset = queryset.filter(
                Q(staff_unique_id=supervisor_staff_id)
                | Q(staff_head_id=supervisor_staff_id)
                | Q(staff_unique_id__in=supervised_staff_ids)
            ).distinct()

        return queryset.order_by("-created_at")

    def _approval_response(self, staff, message):
        return Response(
            {
                "status": True,
                "message": message,
                "data": {
                    "staff_unique_id": staff.staff_unique_id,
                    "employee_name": staff.employee_name,
                    "approval_status": staff.approval_status,
                    "login_enabled": staff.login_enabled,
                    "approved_by": getattr(staff.approved_by, "unique_id", None),
                    "approved_at": staff.approved_at,
                    "rejected_reason": staff.rejected_reason,
                },
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, staff_unique_id=None):
        staff = self.get_object()
        staff.approval_status = Staffcreation.APPROVAL_APPROVED
        staff.login_enabled = True
        staff.approved_by = request.user
        staff.approved_at = timezone.now()
        staff.rejected_reason = None
        staff.save(
            update_fields=[
                "approval_status",
                "login_enabled",
                "approved_by",
                "approved_at",
                "rejected_reason",
                "updated_at",
            ]
        )
        return self._approval_response(staff, "User approved successfully")

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, staff_unique_id=None):
        serializer = StaffApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        staff = self.get_object()
        staff.approval_status = Staffcreation.APPROVAL_REJECTED
        staff.login_enabled = False
        staff.approved_by = None
        staff.approved_at = None
        staff.rejected_reason = serializer.validated_data.get("rejected_reason") or None
        staff.save(
            update_fields=[
                "approval_status",
                "login_enabled",
                "approved_by",
                "approved_at",
                "rejected_reason",
                "updated_at",
            ]
        )
        return self._approval_response(staff, "User rejected successfully")

    @action(detail=True, methods=["post"], url_path="suspend")
    def suspend(self, request, staff_unique_id=None):
        serializer = StaffApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        staff = self.get_object()
        staff.approval_status = Staffcreation.APPROVAL_SUSPENDED
        staff.login_enabled = False
        staff.rejected_reason = serializer.validated_data.get("rejected_reason") or None
        staff.save(
            update_fields=[
                "approval_status",
                "login_enabled",
                "rejected_reason",
                "updated_at",
            ]
        )
        return self._approval_response(staff, "User suspended successfully")

    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, staff_unique_id=None):
        staff = self.get_object()
        staff.approval_status = Staffcreation.APPROVAL_APPROVED
        staff.login_enabled = True
        staff.approved_by = request.user
        staff.approved_at = timezone.now()
        staff.rejected_reason = None
        staff.failed_login_attempts = 0
        staff.save(
            update_fields=[
                "approval_status",
                "login_enabled",
                "approved_by",
                "approved_at",
                "rejected_reason",
                "failed_login_attempts",
                "updated_at",
            ]
        )
        return self._approval_response(staff, "User reactivated successfully")

    @action(detail=False, methods=["get"], url_path="staff-head-options")
    def staff_head_options(self, request):
        # staffusertype_id here names the *new* staff's own role, not a
        # "show me staff of this type" list filter. But the generic
        # ModelFieldQueryFilter backend (reached via self.filter_queryset)
        # treats any ?staffusertype_id= as exactly that — an exact-match
        # filter — which would pre-filter the candidate pool to the selected
        # role itself before the hierarchy lookup below ever runs. So we
        # apply only the tenant (company/project) scoping directly here,
        # bypassing the generic list-filter backend chain entirely, and let
        # the hierarchy config below be the sole source of role filtering.
        base_queryset = Staffcreation.objects.filter(is_deleted=False)
        queryset = self._scope_to_tenant(base_queryset).filter(active_status=True)

        current_id = request.query_params.get("exclude")
        if current_id:
            queryset = queryset.exclude(staff_unique_id=current_id)

        # When the caller tells us which project + role the new/edited staff
        # belongs to, narrow "Staff Head" candidates to whichever role that
        # project's hierarchy config says this role reports to, instead of
        # showing every staff member.
        project_id = request.query_params.get("project_id")
        staffusertype_id = request.query_params.get("staffusertype_id")
        if project_id and staffusertype_id:
            hierarchy_entry = ProjectStaffHierarchy.objects.filter(
                project_id=project_id,
                staffusertype_id=staffusertype_id,
                is_deleted=False,
            ).first()

            if hierarchy_entry and hierarchy_entry.reports_to_staffusertype_id:
                queryset = queryset.filter(
                    project_id=project_id,
                    staffusertype_id=hierarchy_entry.reports_to_staffusertype_id,
                )
            elif hierarchy_entry:
                # Top of the configured chain (e.g. Company Admin) — no head.
                queryset = queryset.none()

        staff_members = list(queryset[:200])
        department_names = {
            department.unique_id: department.department_name
            for department in Department.objects.filter(
                unique_id__in=[staff.department_id for staff in staff_members if staff.department_id],
                is_deleted=False,
            )
        }

        data = [
            {
                "unique_id": staff.staff_unique_id,
                "employee_name": staff.employee_name,
                "department_id": staff.department_id,
                "department_name": department_names.get(staff.department_id),
                "staffusertype_id": staff.staffusertype_id,
                "contractorusertype_id": staff.contractorusertype_id,
            }
            for staff in staff_members
        ]
        return Response(data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            with transaction.atomic():
                # Handle platform superadmin vs company user
                if self._is_platform_super_admin():
                    # Get company from request data for platform superadmin
                    company_unique_id = request.data.get("company_id")
                    if not company_unique_id:
                        from rest_framework.exceptions import ValidationError
                        raise ValidationError({"company_id": "company_id is required"})
                    
                    company = Company.objects.filter(unique_id=company_unique_id).first()
                    if not company:
                        from rest_framework.exceptions import ValidationError
                        raise ValidationError({"company_id": "Invalid company_id"})
                    
                    # Get project from request data
                    # Empty string means "All Projects" (null project) for superadmin
                    raw_project_id = (
                        request.headers.get(self.project_header)
                        or request.data.get("project_id")
                        or request.data.get("project_unique_id")
                    )
                    project_id_explicitly_empty = (
                        "project_id" in request.data and request.data.get("project_id") == ""
                    )
                    if raw_project_id:
                        project = Project.objects.filter(
                            unique_id=raw_project_id,
                        ).filter(
                            Q(company_id=company.unique_id) | Q(company_id=company.name)
                        ).first()
                        if not project:
                            from rest_framework.exceptions import ValidationError
                            raise ValidationError({"project_id": "Invalid project_id for this company"})
                    elif project_id_explicitly_empty:
                        # Superadmin chose "All Projects" — save with null project
                        project = None
                    else:
                        # Get the first active project for the company as default
                        project = Project.objects.filter(
                            is_active=True,
                            is_deleted=False
                        ).filter(
                            Q(company_id=company.unique_id) | Q(company_id=company.name)
                        ).first()
                        if not project:
                            from rest_framework.exceptions import ValidationError
                            raise ValidationError({"project_id": "project_id is required - no active project found for this company"})
                else:
                    # Company user - use scoped methods
                    company = self._company()
                    if not company:
                        from rest_framework.exceptions import PermissionDenied
                        raise PermissionDenied("Company user required")
                    
                    project = self._project()
                    if not project:
                        from rest_framework.exceptions import ValidationError
                        raise ValidationError({"project_id": "project_id is required"})

                # serializer.save(
                #     company_id=company,
                #     project_id=project,
                # )
                instance = serializer.save(
                    company_id=company.unique_id,
                    project_id=project.unique_id if project else None,
                )

            new_data = self._serialize_instance(instance)

            self.log_audit(
                self.request,
                instance=instance,
                previous_data=None,
                new_data=new_data
            )
            return Response(
                {"status": True, "message": "Staff Created Successfully"},
                status=status.HTTP_201_CREATED
            )

        return Response(
            {"status": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=kwargs.pop("partial", False),
        )

        if serializer.is_valid():
            with transaction.atomic():
                company = getattr(instance, "company_id", None) or self._company()
                # If project_id was explicitly sent as "" (all-projects), honour it (None).
                # Otherwise keep the existing project or fall back to the session project.
                if "project_id" in request.data and request.data.get("project_id") == "":
                    project = None
                else:
                    project = serializer.validated_data.get(
                        "project_id", getattr(instance, "project_id", None) or self._project()
                    )
                previous_data = self._serialize_instance(instance)

            updated_instance = serializer.save(
                company_id=company,
                project_id=project,
            )

            new_data = self._serialize_instance(updated_instance)

            self.log_audit(
                self.request,
                instance=updated_instance,
                previous_data=previous_data,
                new_data=new_data
            )
            return Response(
                {"status": True, "message": "Staff Updated Successfully"},
                status=status.HTTP_200_OK
            )

        return Response(
            {"status": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # instance.delete()
        previous_data = self._serialize_instance(instance)

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=None
        )

        instance.delete()

        return Response(
            {"status": True, "message": "Staff Deleted Successfully"},
            status=status.HTTP_200_OK
        )

    # -----------------------------------------------------
    # FCM device token registration (push notifications)
    # Exempted from module-permission checks via
    # ModulePermissionMiddleware.AUTH_ONLY_SUFFIXES ("register-fcm-token/").
    # -----------------------------------------------------

    @action(detail=False, methods=["post"], url_path="register-fcm-token")
    def register_fcm_token(self, request):
        """Driver/operator/supervisor apps call this after login (and on
        token refresh) to register their Firebase device token, so the
        backend can push notifications to this staff member. Always acts on
        the authenticated caller's own record. Mirrors
        CustomercreationViewset.register_fcm_token."""
        staff = request.user
        if not isinstance(staff, Staffcreation):
            return Response(
                {"error": "Only a staff account can register a device token."},
                status=403,
            )
        token = (request.data.get("fcm_token") or "").strip()
        if not token:
            return Response({"error": "fcm_token is required"}, status=400)
        from app.models.masters.customer_masters.customercreation import CustomerCreation

        with transaction.atomic():
            Staffcreation.objects.filter(fcm_token=token).exclude(
                staff_unique_id=staff.staff_unique_id
            ).update(fcm_token=None)
            CustomerCreation.objects.filter(fcm_token=token).update(fcm_token=None)
            staff.fcm_token = token
            staff.save(update_fields=["fcm_token"])
        return Response({"status": "ok"})
