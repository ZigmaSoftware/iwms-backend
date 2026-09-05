"""Master CRUD viewsets for the ticketed complaint workflow.

These replace the `complaint_ticket_stub_viewsets` placeholders, which
returned an empty list / 501 while the models did not exist here yet.
"""

from rest_framework import viewsets

from app.models.complaint_management import (
    ComplaintCategory,
    ComplaintDepartmentMember,
    ComplaintLanguage,
    ComplaintModule,
    ComplaintPriority,
    ComplaintRoutingRule,
    ComplaintSlaRule,
    ComplaintSource,
    ComplaintStatus,
    ComplaintSubcategory,
)
from app.serializers.core_modules.complaint_management.ticket_master_serializers import (
    ComplaintCategorySerializer,
    ComplaintDepartmentMemberSerializer,
    ComplaintLanguageSerializer,
    ComplaintModuleSerializer,
    ComplaintPrioritySerializer,
    ComplaintSlaRuleSerializer,
    ComplaintSourceSerializer,
    ComplaintStatusSerializer,
    ComplaintSubcategorySerializer,
)
from app.serializers.core_modules.complaint_management.ticket_serializers import (
    ComplaintRoutingRuleSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class _BaseComplaintMasterViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    """Soft-deleting master CRUD, shared by every complaint master.

    These masters are global (no company/project FK), so they are owned by the
    superadmin-only "complaint-masters" module. They stay registered under
    "complaint-ticket" as well, but the middleware downgrades that module's
    access to view-only — see MODULE_READONLY_RESOURCES in
    module_permission_middleware.py.
    """

    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-masters"

    def get_queryset(self):
        return self.queryset.filter(is_deleted=False)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])


class ComplaintModuleViewSet(_BaseComplaintMasterViewSet):
    queryset = ComplaintModule.objects.all()
    serializer_class = ComplaintModuleSerializer
    permission_resource = "ComplaintModule"
    AUDIT_ENDPOINT = "modules"


class ComplaintPriorityViewSet(_BaseComplaintMasterViewSet):
    queryset = ComplaintPriority.objects.all()
    serializer_class = ComplaintPrioritySerializer
    permission_resource = "ComplaintPriority"
    AUDIT_ENDPOINT = "priorities"


class ComplaintStatusViewSet(_BaseComplaintMasterViewSet):
    queryset = ComplaintStatus.objects.all()
    serializer_class = ComplaintStatusSerializer
    permission_resource = "ComplaintStatus"
    AUDIT_ENDPOINT = "statuses"


class ComplaintSourceViewSet(_BaseComplaintMasterViewSet):
    queryset = ComplaintSource.objects.all()
    serializer_class = ComplaintSourceSerializer
    permission_resource = "ComplaintSource"
    AUDIT_ENDPOINT = "sources"


class ComplaintLanguageViewSet(_BaseComplaintMasterViewSet):
    queryset = ComplaintLanguage.objects.all()
    serializer_class = ComplaintLanguageSerializer
    permission_resource = "ComplaintLanguage"
    AUDIT_ENDPOINT = "languages"


class _ScopedComplaintMasterViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    """Soft-deleting CRUD for the company/project-scoped complaint masters.

    Category, Sub-category, SLA and routing rules all carry company/project
    (migration 0003), because which complaint types a project offers, their
    priorities, the department they route to and the resolution targets are
    all per-project operational choices. `CompanyScopedViewSet.filter_queryset`
    applies the scope and stamps it on create; this only adds the
    soft-delete filter the module uses everywhere.
    """

    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-masters"

    def get_queryset(self):
        return self.queryset.filter(is_deleted=False)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        if instance.is_active:
            instance.is_active = False
            instance.save(update_fields=["is_active"])


class ComplaintTicketCategoryViewSet(_ScopedComplaintMasterViewSet):
    queryset = ComplaintCategory.objects.select_related(
        "module", "default_priority", "default_department"
    )
    serializer_class = ComplaintCategorySerializer
    permission_resource = "ComplaintCategory"
    AUDIT_ENDPOINT = "ticket-categories"


class ComplaintTicketSubcategoryViewSet(_ScopedComplaintMasterViewSet):
    queryset = ComplaintSubcategory.objects.select_related("category", "default_priority")
    serializer_class = ComplaintSubcategorySerializer
    permission_resource = "ComplaintSubcategory"
    AUDIT_ENDPOINT = "ticket-subcategories"

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category_id=category)
        return qs


class ComplaintSlaRuleViewSet(_ScopedComplaintMasterViewSet):
    queryset = ComplaintSlaRule.objects.select_related(
        "category", "subcategory", "priority", "source"
    )
    serializer_class = ComplaintSlaRuleSerializer
    permission_resource = "ComplaintSlaRule"
    AUDIT_ENDPOINT = "sla-rules"


class ComplaintRoutingRuleViewSet(_ScopedComplaintMasterViewSet):
    queryset = ComplaintRoutingRule.objects.select_related(
        "category", "subcategory", "priority", "department", "sla_rule"
    )
    serializer_class = ComplaintRoutingRuleSerializer
    permission_resource = "ComplaintRoutingRule"
    AUDIT_ENDPOINT = "routing-rules"


class ComplaintDepartmentMemberViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    """Department roster CRUD: who belongs to a department for complaint
    assignment purposes, and who its (single) supervisor is.

    Company-scoped since a roster row points at company-scoped
    `Department`/`StaffcreationOfficeDetails` data, so each company owns
    its own roster.
    """

    queryset = ComplaintDepartmentMember.objects.select_related("department", "staff")
    serializer_class = ComplaintDepartmentMemberSerializer
    permission_resource = "ComplaintDepartmentMember"
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "department-members"

    def get_queryset(self):
        return self.queryset.filter(is_deleted=False)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        if instance.is_active:
            instance.is_active = False
            instance.save(update_fields=["is_active"])
