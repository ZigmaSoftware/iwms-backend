from django.db.models import Q
from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from app.models.core_modules.complaint_management import (
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
        self.perform_destroy(instance)
        return Response({"message": "Deleted successfully"}, status=status.HTTP_200_OK)


class ComplaintRoutingRuleViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    # category/subcategory/priority/sla_rule are resolver @properties over
    # plain id CharFields now (not real relations), and "team" was never a
    # field on this model — select_related can no longer be used here.
    queryset = ComplaintRoutingRule.objects.filter(is_deleted=False).order_by("unique_id")
    serializer_class = ComplaintRoutingRuleSerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "routing-rules"


class ComplaintFeedbackViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ComplaintFeedbackSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    ordering_fields = ["submitted_at", "rating"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "feedback"

    def get_queryset(self):
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket

        qs = ComplaintFeedback.objects.filter(is_deleted=False).order_by("-submitted_at")
        ticket = self.request.query_params.get("ticket")
        if ticket:
            qs = qs.filter(ticket_id=ticket)
        # Feedback carries no company/project of its own — it hangs off a
        # ticket, which does. Filter through the parent so the Feedback list
        # can offer the same Company/Project pickers as every other
        # company-scoped list.
        company_id = self.request.query_params.get("company_id")
        project_id = self.request.query_params.get("project_id")
        if company_id or project_id:
            ticket_filter = {}
            if company_id:
                ticket_filter["company_id"] = company_id
            if project_id:
                ticket_filter["project_id"] = project_id
            matching_ticket_ids = ComplaintTicket.objects.filter(**ticket_filter).values("unique_id")
            qs = qs.filter(ticket_id__in=matching_ticket_ids)
        search = self.request.query_params.get("search")
        if search:
            matching_ticket_ids = ComplaintTicket.objects.filter(
                Q(ticket_no__icontains=search) | Q(unique_id__icontains=search)
            ).values("unique_id")
            from app.models.masters.customer_masters.customercreation import CustomerCreation
            matching_customer_ids = CustomerCreation.objects.filter(
                customer_name__icontains=search,
            ).values("unique_id")
            qs = qs.filter(
                Q(ticket_id__in=matching_ticket_ids) | Q(customer_id__in=matching_customer_ids)
            )
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
