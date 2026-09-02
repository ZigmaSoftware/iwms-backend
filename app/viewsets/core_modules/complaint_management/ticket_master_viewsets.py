"""Master CRUD viewsets for the ticketed complaint workflow.

These replace the `complaint_ticket_stub_viewsets` placeholders, which
returned an empty list / 501 while the models did not exist here yet.
"""

from rest_framework import viewsets

from app.models.complaint_management import (
    ComplaintCategory,
    ComplaintLanguage,
    ComplaintModule,
    ComplaintPriority,
    ComplaintRoutingRule,
    ComplaintSlaRule,
    ComplaintSource,
    ComplaintStatus,
    ComplaintSubcategory,
    ComplaintTeam,
)
from app.serializers.core_modules.complaint_management.ticket_master_serializers import (
    ComplaintCategorySerializer,
    ComplaintLanguageSerializer,
    ComplaintModuleSerializer,
    ComplaintPrioritySerializer,
    ComplaintSlaRuleSerializer,
    ComplaintSourceSerializer,
    ComplaintStatusSerializer,
    ComplaintSubcategorySerializer,
    ComplaintTeamSerializer,
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


class ComplaintTeamViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    """Teams stay in the CORE MODULES "complaint-ticket" module.

    Unlike the other masters in this file, a team points at company-scoped
    data (Department, StaffcreationOfficeDetails), so it is operational rather
    than global configuration and each company owns its own crews / escalation
    chain. It therefore extends `CompanyScopedViewSet` — not the plain
    `_BaseComplaintMasterViewSet` the global masters use — so every list is
    filtered to the caller's company/project and creates are stamped with it.
    Without that, one company's supervisor would see every other company's
    teams in the assign dropdown.
    """

    queryset = ComplaintTeam.objects.select_related("department", "lead_staff", "escalates_to")
    serializer_class = ComplaintTeamSerializer
    permission_resource = "ComplaintTeam"
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "teams"

    def get_queryset(self):
        # The company/project filter is applied by
        # `CompanyScopedViewSet.filter_queryset`, not here — this only adds
        # the soft-delete filter every master in this module uses.
        return self.queryset.filter(is_deleted=False)

    def perform_destroy(self, instance):
        # The base soft-deletes and stamps `updated_by`; deactivating as well
        # is this module's convention, so defer to it and then clear the flag.
        super().perform_destroy(instance)
        if instance.is_active:
            instance.is_active = False
            instance.save(update_fields=["is_active"])


class _ScopedComplaintMasterViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    """Soft-deleting CRUD for the company/project-scoped complaint masters.

    Category, Sub-category, SLA and routing rules all carry company/project
    (migration 0003), because which complaint types a project offers, their
    priorities, the team they route to and the resolution targets are all
    per-project operational choices. `CompanyScopedViewSet.filter_queryset`
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
    queryset = ComplaintCategory.objects.select_related("module", "default_priority", "default_team")
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
        "category", "subcategory", "priority", "source", "escalation_team"
    )
    serializer_class = ComplaintSlaRuleSerializer
    permission_resource = "ComplaintSlaRule"
    AUDIT_ENDPOINT = "sla-rules"


class ComplaintRoutingRuleViewSet(_ScopedComplaintMasterViewSet):
    queryset = ComplaintRoutingRule.objects.select_related(
        "category", "subcategory", "priority", "team", "sla_rule"
    )
    serializer_class = ComplaintRoutingRuleSerializer
    permission_resource = "ComplaintRoutingRule"
    AUDIT_ENDPOINT = "routing-rules"
