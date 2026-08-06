"""Citizen-facing complaint ticket endpoints for the mobile app.

Ported from the government backend's `citizen_viewset.py`
(`CitizenComplaintTicketViewSet`). The public/no-login grievance intake and
the local-body picker actions live separately in `public_grievance_viewset.py`
(this project has no Corporation/Municipality/TownPanchayat local bodies to
offer, so its geo pickers are state/district/panchayat/zone/ward instead).

Registered under the `citizen/` URL group, which
`ModulePermissionMiddleware.AUTH_ONLY_SUFFIXES` exempts from module
permission checks - access is gated purely by JWT authentication, and every
query is hard-scoped to the logged-in citizen so a citizen can only ever
see/raise their own tickets.

Routing/SLA auto-assignment now runs via
`app.services.complaint_ticket_routing.apply_routing_and_sla` right after a
ticket is created, same as the public grievance intake.
"""

from django.db import transaction
from django.db.models import Q
from rest_framework import status as http_status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.models.customers.customercreation import CustomerCreation
from app.models.complaint_management import (
    ComplaintCategory,
    ComplaintFeedback,
    ComplaintPriority,
    ComplaintSource,
    ComplaintStatus,
    ComplaintStatusHistory,
    ComplaintSubcategory,
    ComplaintTicket,
)
from app.serializers.core_modules.complaint_management.ticket_serializers import (
    ComplaintFeedbackSerializer,
    ComplaintTicketDetailSerializer,
    ComplaintTicketSerializer,
)
from app.services.complaint_ticket_routing import apply_routing_and_sla

# Statuses that count as "final" for feedback purposes - a citizen should be
# able to rate a ticket as soon as it is resolved, not only once staff
# separately mark it closed.
FEEDBACK_ELIGIBLE_STATUS_CODES = {"RESOLVED", "CLOSED", "REJECTED", "CANCELLED"}

# Flat geo copied from the customer onto their ticket, mirroring this
# project's Zone/Ward-under-Company/Project model (see `ticket.py`).
# (ticket field name, customer FK attribute name) — the customer's panchayat
# FK is named `panchayat_id` (not `panchayat`) unlike the others.
CUSTOMER_GEO_FIELDS = (
    ("state", "state"),
    ("district", "district"),
    ("panchayat", "panchayat_id"),
    ("zone", "zone"),
    ("ward", "ward"),
)


def _as_customer(request):
    user = getattr(request, "user", None)
    return user if isinstance(user, CustomerCreation) else None


class CitizenComplaintTicketViewSet(viewsets.ViewSet):
    """My-tickets API for citizens (mobile app)."""

    permission_classes = [IsAuthenticated]

    def _scoped_qs(self, customer):
        return (
            ComplaintTicket.objects.filter(is_deleted=False)
            .select_related(
                "category", "subcategory", "priority", "status", "source",
                "assigned_team", "assigned_team__department", "assigned_staff",
            )
            .prefetch_related("status_history", "status_history__to_status", "attachments")
            .filter(Q(customer=customer) | Q(wa_phone=customer.contact_no))
            .order_by("-created")
        )

    # ---- GET /citizen/complaint-tickets/ ----
    def list(self, request):
        customer = _as_customer(request)
        if not customer:
            return Response([], status=http_status.HTTP_200_OK)
        data = ComplaintTicketSerializer(
            self._scoped_qs(customer), many=True, context={"request": request}
        ).data
        return Response(data)

    # ---- GET /citizen/complaint-tickets/{id}/ ----
    def retrieve(self, request, pk=None):
        customer = _as_customer(request)
        ticket = self._scoped_qs(customer).filter(unique_id=pk).first() if customer else None
        if not ticket:
            return Response({"detail": "Ticket not found."}, status=http_status.HTTP_404_NOT_FOUND)
        return Response(ComplaintTicketDetailSerializer(ticket, context={"request": request}).data)

    # ---- POST /citizen/complaint-tickets/ ----
    @transaction.atomic
    def create(self, request):
        customer = _as_customer(request)
        if not customer:
            return Response(
                {"detail": "Only a logged-in citizen can raise a complaint here."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        data = request.data
        category = ComplaintCategory.objects.filter(
            unique_id=data.get("category"), is_deleted=False
        ).first()
        if not category:
            return Response({"category": "This field is required."}, status=http_status.HTTP_400_BAD_REQUEST)

        subcategory = ComplaintSubcategory.objects.filter(
            unique_id=data.get("subcategory"), is_deleted=False
        ).first()
        priority = (
            ComplaintPriority.objects.filter(unique_id=data.get("priority"), is_deleted=False).first()
            or category.default_priority
        )
        status_obj = (
            ComplaintStatus.objects.filter(status_code="SUBMITTED", is_deleted=False).first()
            or ComplaintStatus.objects.filter(status_code="DRAFT", is_deleted=False).first()
        )
        source = (
            ComplaintSource.objects.filter(source_code="MOBILE_APP", is_deleted=False).first()
            or ComplaintSource.objects.filter(source_code="WHATSAPP", is_deleted=False).first()
        )
        if not priority or not status_obj:
            return Response(
                {"detail": "Complaint ticket masters are not configured. Run seed_complaint_masters."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        description = str(data.get("description") or "").strip()
        customer_geo = {
            f"{ticket_field}_id": getattr(customer, f"{customer_attr}_id", None)
            for ticket_field, customer_attr in CUSTOMER_GEO_FIELDS
        }
        ticket = ComplaintTicket.objects.create(
            company_id_id=getattr(customer, "company_id_id", None),
            project_id_id=getattr(customer, "project_id_id", None),
            customer=customer,
            category=category,
            subcategory=subcategory,
            priority=priority,
            status=status_obj,
            source=source,
            title=(description or category.category_name)[:120],
            description=description,
            location_text=str(data.get("location_text") or ""),
            wa_phone=customer.contact_no,
            profile_name=customer.customer_name,
            **customer_geo,
        )
        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=None,
            to_status=status_obj,
            changed_by_customer=customer,
            changed_by_system=False,
            remarks="Raised via mobile app",
            visible_to_citizen=True,
        )
        apply_routing_and_sla(ticket, save=True)
        return Response(
            ComplaintTicketDetailSerializer(ticket, context={"request": request}).data,
            status=http_status.HTTP_201_CREATED,
        )

    # ---- POST /citizen/complaint-tickets/{id}/feedback/ ----
    @action(detail=True, methods=["post"])
    def feedback(self, request, pk=None):
        """Citizen rates a resolved/closed ticket. One feedback per ticket —
        resubmitting updates it rather than erroring."""
        customer = _as_customer(request)
        ticket = self._scoped_qs(customer).filter(unique_id=pk).first() if customer else None
        if not ticket:
            return Response({"detail": "Ticket not found."}, status=http_status.HTTP_404_NOT_FOUND)
        status_code = getattr(ticket.status, "status_code", None)
        if status_code not in FEEDBACK_ELIGIBLE_STATUS_CODES:
            return Response(
                {"detail": "Feedback can only be submitted once the ticket is resolved or closed."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        feedback, _ = ComplaintFeedback.objects.update_or_create(
            ticket=ticket,
            defaults={
                "customer": customer,
                "rating": request.data.get("rating"),
                "feedback_text": request.data.get("feedback_text"),
                "is_issue_solved": bool(request.data.get("is_issue_solved", False)),
            },
        )
        return Response(ComplaintFeedbackSerializer(feedback).data, status=http_status.HTTP_201_CREATED)

    # ---- GET /citizen/complaint-tickets/meta/ ----
    @action(detail=False, methods=["get"])
    def meta(self, request):
        """Categories (+subcategories) + priorities so the chat can offer choices."""
        cats = ComplaintCategory.objects.filter(is_deleted=False, is_active=True).order_by("sort_order")
        subs = ComplaintSubcategory.objects.filter(is_deleted=False, is_active=True).order_by("sort_order")
        pris = ComplaintPriority.objects.filter(is_deleted=False, is_active=True).order_by("sort_order")
        return Response({
            "categories": [
                {
                    "unique_id": c.unique_id,
                    "category_code": c.category_code,
                    "category_name": c.category_name,
                    "default_priority": c.default_priority_id,
                    "default_priority_code": getattr(c.default_priority, "priority_code", None),
                    "requires_location": c.requires_location,
                }
                for c in cats
            ],
            "subcategories": [
                {
                    "unique_id": s.unique_id,
                    "category": s.category_id,
                    "subcategory_name": s.subcategory_name,
                }
                for s in subs
            ],
            "priorities": [
                {"unique_id": p.unique_id, "priority_code": p.priority_code, "priority_name": p.priority_name}
                for p in pris
            ],
        })
