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


class _BaseComplaintMasterViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    """Soft-deleting master CRUD, shared by every complaint master."""

    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"

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


class ComplaintTeamViewSet(_BaseComplaintMasterViewSet):
    queryset = ComplaintTeam.objects.select_related("department", "lead_staff", "escalates_to")
    serializer_class = ComplaintTeamSerializer
    permission_resource = "ComplaintTeam"
    AUDIT_ENDPOINT = "teams"


class ComplaintTicketCategoryViewSet(_BaseComplaintMasterViewSet):
    queryset = ComplaintCategory.objects.select_related("module", "default_priority", "default_team")
    serializer_class = ComplaintCategorySerializer
    permission_resource = "ComplaintCategory"
    AUDIT_ENDPOINT = "ticket-categories"


class ComplaintTicketSubcategoryViewSet(_BaseComplaintMasterViewSet):
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


class ComplaintSlaRuleViewSet(_BaseComplaintMasterViewSet):
    queryset = ComplaintSlaRule.objects.select_related(
        "category", "subcategory", "priority", "source", "escalation_team"
    )
    serializer_class = ComplaintSlaRuleSerializer
    permission_resource = "ComplaintSlaRule"
    AUDIT_ENDPOINT = "sla-rules"


class ComplaintRoutingRuleViewSet(_BaseComplaintMasterViewSet):
    queryset = ComplaintRoutingRule.objects.select_related(
        "category", "subcategory", "priority", "team", "sla_rule"
    )
    serializer_class = ComplaintRoutingRuleSerializer
    permission_resource = "ComplaintRoutingRule"
    AUDIT_ENDPOINT = "routing-rules"
