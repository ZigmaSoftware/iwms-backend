from django.db.models import Q
from django.http import Http404
from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.models.core_modules.complaint_management import (
    ComplaintCategory,
    ComplaintStatus,
    ComplaintTicket,
)
from app.models.core_modules.complaint_management.transactions import (
    ComplaintEscalationHistory,
)
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.services.complaint_audit import summarize_tickets, ticket_timeline
from app.utils.audit_context import is_platform_super_admin
from app.utils.pagination import LimitOffsetWithPage


class ComplaintAuditViewSet(viewsets.ViewSet):
    """
    Read-only Complaint Audit: per ticket, when it was raised, how it was
    resolved (resolution remarks), why it was reopened, its escalations and
    how long it took. Assembled on read by app.services.complaint_audit from
    the ticket's history rows; deleted tickets are included so their delete
    reason stays visible.
    """

    permission_classes = [IsAuthenticated]
    # Matches the "complaint-audit" UserScreen and the "audits" allowlist
    # entry in ModulePermissionMiddleware.
    permission_resource = "ComplaintAudit"
    lookup_field = "unique_id"

    def _scoped_base_queryset(self):
        """Tenancy gate, matching StaticRouteAuditLogViewSet: a platform super
        admin sees every company's tickets; a company user only their own."""
        queryset = ComplaintTicket.objects.all().order_by("-created", "-pk")
        user = self.request.user

        if is_platform_super_admin(user):
            return queryset

        company = getattr(user, "company_id", None)
        company_uid = str(getattr(company, "unique_id", company) or "") or None
        if not company_uid:
            raise PermissionDenied("Company user required")
        return queryset.filter(company_id=company_uid)

    def get_queryset(self):
        queryset = self._scoped_base_queryset()
        params = self.request.query_params

        company_id = params.get("company_id") or params.get("company_unique_id")
        if company_id and is_platform_super_admin(self.request.user):
            queryset = queryset.filter(company_id=company_id)

        project_id = params.get("project_id") or params.get("project_unique_id")
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        status_codes = [c for c in (params.get("status") or "").upper().split(",") if c]
        if status_codes:
            status_ids = ComplaintStatus.objects.filter(status_code__in=status_codes).values("unique_id")
            queryset = queryset.filter(status_id__in=status_ids)

        category = params.get("category")
        if category:
            queryset = queryset.filter(category_id=category)

        if params.get("reopened") in ("1", "true"):
            queryset = queryset.filter(reopened_count__gt=0)

        if params.get("escalated") in ("1", "true"):
            escalated_ids = ComplaintEscalationHistory.objects.filter(is_deleted=False).values("ticket_id")
            queryset = queryset.filter(unique_id__in=escalated_ids)

        deleted = params.get("deleted")
        if deleted == "only":
            queryset = queryset.filter(is_deleted=True)
        elif deleted == "exclude":
            queryset = queryset.filter(is_deleted=False)

        date_from = parse_date(params.get("date_from") or "")
        if date_from:
            queryset = queryset.filter(created__date__gte=date_from)

        date_to = parse_date(params.get("date_to") or "")
        if date_to:
            queryset = queryset.filter(created__date__lte=date_to)

        search = (params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(ticket_no__icontains=search)
                | Q(title__icontains=search)
                | Q(profile_name__icontains=search)
                | Q(wa_phone__icontains=search)
            )

        return queryset

    def list(self, request):
        queryset = self.get_queryset()
        paginator = LimitOffsetWithPage()
        page = paginator.paginate_queryset(queryset, request, view=self)
        if page is None:
            return Response(summarize_tickets(queryset))
        return paginator.get_paginated_response(summarize_tickets(page))

    def retrieve(self, request, unique_id=None):
        ticket = self._scoped_base_queryset().filter(unique_id=unique_id).first()
        if ticket is None:
            raise Http404
        return Response({**summarize_tickets([ticket])[0], **ticket_timeline(ticket)})

    @action(detail=False, methods=["get"], url_path="filter-options")
    def filter_options(self, request):
        """Company / project / status / category choices for the list page's
        dropdowns. Companies and projects come from the scoped tickets, so a
        company user is never offered another company."""
        unordered = self._scoped_base_queryset().order_by()
        company_id = request.query_params.get("company_id")
        project_source = unordered.filter(company_id=company_id) if company_id else unordered

        def options(model, source, field):
            ids = [v for v in source.values_list(field, flat=True).distinct() if v]
            rows = model.objects.filter(unique_id__in=ids).values_list("unique_id", "name")
            return sorted(
                ({"unique_id": uid, "name": name or uid} for uid, name in rows),
                key=lambda o: o["name"].lower(),
            )

        return Response({
            "companies": options(Company, unordered, "company_id"),
            "projects": options(Project, project_source, "project_id"),
            "statuses": [
                {"unique_id": code, "name": name}
                for code, name in ComplaintStatus.objects.filter(is_deleted=False)
                .order_by("sort_order")
                .values_list("status_code", "status_name")
            ],
            "categories": sorted(
                (
                    {"unique_id": uid, "name": name or uid}
                    for uid, name in ComplaintCategory.objects.filter(
                        unique_id__in=[v for v in unordered.values_list("category_id", flat=True).distinct() if v]
                    ).values_list("unique_id", "category_name")
                ),
                key=lambda o: o["name"].lower(),
            ),
        })
