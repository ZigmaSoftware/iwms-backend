from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from app.models.complaint_management import (
    ComplaintFeedback,
    ComplaintReopenHistory,
    ComplaintRoutingRule,
)
from app.serializers.core_modules.complaint_management.ticket_serializers import (
    ComplaintFeedbackSerializer,
    ComplaintReopenHistorySerializer,
    ComplaintRoutingRuleSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage


class _SoftDeleteMixin:
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])
        return Response({"message": "Deleted successfully"}, status=status.HTTP_200_OK)


class ComplaintRoutingRuleViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = ComplaintRoutingRule.objects.filter(is_deleted=False).select_related(
        "category", "subcategory", "priority", "team", "sla_rule"
    ).order_by("unique_id")
    serializer_class = ComplaintRoutingRuleSerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "routing-rules"


class ComplaintFeedbackViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ComplaintFeedbackSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["ticket__ticket_no", "ticket__unique_id", "customer__customer_name"]
    ordering_fields = ["submitted_at", "rating"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "feedback"

    def get_queryset(self):
        qs = ComplaintFeedback.objects.filter(is_deleted=False).select_related(
            "ticket", "customer"
        ).order_by("-submitted_at")
        ticket = self.request.query_params.get("ticket")
        if ticket:
            qs = qs.filter(ticket_id=ticket)
        # Feedback carries no company/project of its own — it hangs off a
        # ticket, which does. Filter through the parent so the Feedback list
        # can offer the same Company/Project pickers as every other
        # company-scoped list.
        company_id = self.request.query_params.get("company_id")
        if company_id:
            qs = qs.filter(ticket__company_id=company_id)
        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(ticket__project_id=project_id)
        return qs


class ComplaintReopenHistoryViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ComplaintReopenHistorySerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "reopen-history"

    def get_queryset(self):
        qs = ComplaintReopenHistory.objects.filter(is_deleted=False).order_by("-reopened_at")
        ticket = self.request.query_params.get("ticket")
        if ticket:
            qs = qs.filter(ticket_id=ticket)
        return qs
