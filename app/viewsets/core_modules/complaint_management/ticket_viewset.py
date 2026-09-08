"""Supervisor / staff complaint ticket API.

Ported from the government backend's `ticket_viewset.py`
(`ComplaintTicketViewSet`). Scoping follows this project's model:
Company/Project tenancy (via `CompanyScopedViewSet`) plus Zone/Ward instead
of government's District + five-local-body hierarchy. Assignment
notifications go through this project's `staff_notification_service`
(in-app only — no push-to-citizen-device yet).
"""

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils import timezone
from rest_framework import filters, status as http_status
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.complaint_management import (
    ComplaintAttachment,
    ComplaintComment,
    ComplaintFeedback,
    ComplaintReopenHistory,
    ComplaintStatus,
    ComplaintStatusHistory,
    ComplaintTicket,
)
from app.serializers.core_modules.complaint_management.ticket_serializers import (
    ComplaintAttachmentSerializer,
    ComplaintCommentSerializer,
    ComplaintFeedbackSerializer,
    ComplaintTicketDetailSerializer,
    ComplaintTicketSerializer,
)
from app.services.complaint_ticket_routing import (
    CLOSED_STATUS_CODES,
    apply_routing_and_sla,
    perform_escalation,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet

User = get_user_model()


# Source code written by `PublicGrievanceViewSet` for anonymous intake.
PUBLIC_SOURCE_CODE = "PUBLIC_GRIEVANCE"


def _actor_user(request):
    """Return the request user only if it is an auth User.

    Staff log in as `StaffcreationOfficeDetails` (not the auth User model),
    so the history models' *_by_user FKs (-> AUTH_USER_MODEL) must be left
    null for staff actors.
    """
    user = getattr(request, "user", None)
    return user if isinstance(user, User) else None


def _resolve_status(status_code):
    return ComplaintStatus.objects.filter(status_code=status_code, is_deleted=False).first()


def _status_bucket_q(bucket):
    if bucket == "pending":
        return models.Q(status__status_code__in=["SUBMITTED", "ASSIGNED"])
    if bucket == "started":
        return models.Q(status__status_code="IN_PROGRESS")
    if bucket == "escalated":
        return models.Q(status__status_code="ESCALATED")
    if bucket == "resolved":
        return models.Q(status__status_code__in=CLOSED_STATUS_CODES)
    if bucket == "open":
        return ~models.Q(status__status_code__in=CLOSED_STATUS_CODES)
    return models.Q()


def _is_platform_superuser(user):
    return bool(getattr(user, "is_superuser", False) and getattr(user, "company_id", None) is None)


def _is_entry_level_staff(user):
    """Whether `user` holds their project's *effective* entry hierarchy
    level — the level tickets are actually first assigned to, once SLA
    rules have disabled lower levels (e.g. Driver/Operator) as configured
    through the SLA Rule screen's Escalation Levels. That person sees every
    ticket in their geo scope (see `_entry_level_ticket_scope`); everyone at
    a higher level (Project Admin, Company Admin, ...) only sees tickets
    that have actually escalated up to them.

    The effective entry level isn't a fixed project setting — a project's
    `ProjectStaffHierarchy` might define Driver/Operator/Supervisor/Project
    Admin/Company Admin, but different SLA rules (per category/priority) can
    each disable a different subset of the lower levels. This takes the
    lowest level that is enabled on ANY of the project's SLA rules as the
    project's overall entry point — the same level `apply_routing_and_sla`
    would use for a ticket whose SLA rule doesn't narrow it further.

    A staff record with no `staffusertype_id`/`project_id`, or a project
    with no `ProjectStaffHierarchy`/enabled `ComplaintSlaEscalationLevel` at
    all, is treated as entry-level (fails open to "sees everything in their
    scope") so a deployment that hasn't configured hierarchy/SLA levels yet
    keeps working as before rather than hiding tickets from everyone.
    """
    from app.models.complaint_management.masters import ComplaintSlaEscalationLevel
    from app.models.role_assigns.projectStaffHierarchy import ProjectStaffHierarchy

    staffusertype_id = getattr(user, "staffusertype_id_id", None)
    project_id = getattr(user, "project_id_id", None)
    if not staffusertype_id or not project_id:
        return True

    hierarchy_levels = dict(
        ProjectStaffHierarchy.objects.filter(
            project_id=project_id, is_deleted=False,
        ).values_list("staffusertype_id_id", "level")
    )
    if not hierarchy_levels:
        return True

    own_level = hierarchy_levels.get(staffusertype_id)
    if own_level is None:
        return True

    enabled_levels = set(
        ComplaintSlaEscalationLevel.objects.filter(
            is_enabled=True,
            is_deleted=False,
            sla_rule__project_id=project_id,
            sla_rule__is_deleted=False,
        ).values_list("level", flat=True)
    )
    if not enabled_levels:
        # No SLA rule has any escalation level configured for this project
        # yet — fall back to the raw hierarchy's lowest level.
        entry_level = min(hierarchy_levels.values())
    else:
        entry_level = min(enabled_levels)

    return own_level == entry_level


def _entry_level_ticket_scope(user):
    """Geo scope for an entry-level staff member's "sees every ticket"
    view — narrowed to their `StaffAccessConfiguration` zone/panchayat/ward
    grants using the same "narrowest non-empty grant wins, empty means
    unrestricted at that level" rule as escalation routing (see
    `complaint_ticket_routing._staff_geo_matches`). A staff member with no
    access configuration, or none of the three grants populated, is
    unrestricted — they see every ticket in their company/project.
    """
    access_config = user.access_configuration.filter(is_active=True, is_deleted=False).first()
    if not access_config:
        return models.Q()

    wards = list(access_config.wards.values_list("unique_id", flat=True))
    if wards:
        return models.Q(ward_id__in=wards)

    panchayats = list(access_config.panchayats.values_list("unique_id", flat=True))
    if panchayats:
        return models.Q(panchayat_id__in=panchayats)

    zones = list(access_config.zones.values_list("unique_id", flat=True))
    if zones:
        return models.Q(zone_id__in=zones)

    return models.Q()


class ComplaintTicketViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    serializer_class = ComplaintTicketSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["ticket_no", "wa_phone", "profile_name", "title", "description", "customer__customer_name"]
    ordering_fields = ["created", "updated", "next_escalation_due_at", "ticket_no"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "tickets"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ComplaintTicketDetailSerializer
        return ComplaintTicketSerializer

    def get_queryset(self):
        qs = ComplaintTicket.objects.filter(is_deleted=False).select_related(
            "category", "subcategory", "priority", "status", "source",
            "customer", "assigned_staff", "escalated_to_staff",
            "state", "district", "panchayat", "zone", "ward",
        ).prefetch_related(
            "status_history", "status_history__to_status",
            "escalation_history",
            "attachments", "extra_details",
        ).order_by("-created")
        params = self.request.query_params

        if self.action in ("list", "counts"):
            customer = params.get("customer") or params.get("customer_id")
            if customer:
                qs = qs.filter(customer_id=customer)
            wa_phone = params.get("wa_phone")
            if wa_phone:
                qs = qs.filter(wa_phone=wa_phone)
            state = params.get("state")
            if state:
                qs = qs.filter(state_id=state)
            district = params.get("district")
            if district:
                qs = qs.filter(district_id=district)
            # The Desk offers a panchayat dropdown; without this the selection
            # was accepted and silently ignored, so the list never narrowed.
            panchayat = params.get("panchayat")
            if panchayat:
                qs = qs.filter(panchayat_id=panchayat)
            zone = params.get("zone")
            if zone:
                qs = qs.filter(zone_id=zone)
            ward = params.get("ward")
            if ward:
                qs = qs.filter(ward_id=ward)
            assigned_staff = params.get("assigned_staff")
            if assigned_staff:
                qs = qs.filter(assigned_staff_id=assigned_staff)
            escalated = params.get("escalated")
            if escalated in ("1", "true", "True"):
                qs = qs.filter(is_escalated=True)
            # Intake origin. "public" is anything raised through the no-login
            # public grievance form; "internal" is everything else (admin,
            # call-centre, mobile app). The Desk's tabs send these two words
            # rather than a ComplaintSource id, because a deployment can have
            # several internal sources and the tab means "not public".
            source = (params.get("source") or "").strip().lower()
            if source == "public":
                qs = qs.filter(source__source_code=PUBLIC_SOURCE_CODE)
            elif source == "internal":
                qs = qs.exclude(source__source_code=PUBLIC_SOURCE_CODE)
            elif source:
                # Any other value is treated as a ComplaintSource id, so the
                # API can still filter to one specific source.
                qs = qs.filter(source_id=source)

            status_code = params.get("status")
            if status_code:
                normalized = status_code.strip().lower()
                bucket = {
                    "in_progress": "started",
                    "progressing": "started",
                    "processing": "started",
                    "new": "pending",
                }.get(normalized, normalized)
                q = _status_bucket_q(bucket)
                if q:
                    qs = qs.filter(q)
                else:
                    qs = qs.filter(status__status_code=status_code)

        # Per-staff scoping, by hierarchy level rather than role name:
        #   - A platform superuser sees everything.
        #   - The entry-level staff for their project (typically Supervisor —
        #     see `_is_entry_level_staff`) sees every ticket in their geo
        #     scope (their StaffAccessConfiguration zone/panchayat/ward
        #     grants, or everything in their company/project if unrestricted).
        #   - Everyone above entry level (Project Admin, Company Admin, ...)
        #     only sees tickets currently escalated to them — they aren't
        #     involved until a breach actually escalates a ticket their way.
        user = getattr(self.request, "user", None)
        is_staff_record = hasattr(user, "staff_unique_id")
        wants_all = params.get("all") in ("1", "true", "True")
        if is_staff_record and not wants_all and not _is_platform_superuser(user):
            if _is_entry_level_staff(user):
                qs = qs.filter(_entry_level_ticket_scope(user))
            else:
                qs = qs.filter(escalated_to_staff=user)
        return qs

    @action(detail=False, methods=["get"], url_path="counts")
    def counts(self, request):
        qs = self.filter_queryset(self.get_queryset())
        total = qs.count()
        public = qs.filter(source__source_code=PUBLIC_SOURCE_CODE).count()
        return Response({
            "all": total,
            "public": public,
            "internal": total - public,
        })

    def perform_create(self, serializer):
        super().perform_create(serializer)  # tenancy + audit (CompanyScopedViewSet)
        ticket = serializer.instance
        apply_routing_and_sla(ticket, save=True)
        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=None,
            to_status=ticket.status,
            changed_by_system=True,
            remarks="Ticket created",
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])
        return Response({"message": "Ticket deleted successfully"}, status=http_status.HTTP_200_OK)

    def _finalize_and_backfill(self, ticket):
        """Call after a ticket's status is saved as one of the closed codes.

        Clears any escalation flag — a closed ticket has nothing left to
        escalate.
        """
        if ticket.is_escalated:
            ticket.is_escalated = False
            ticket.escalated_to_staff = None
            ticket.save(update_fields=["is_escalated", "escalated_to_staff"])

    # ---- PATCH/POST /tickets/{id}/status/ ----
    @action(detail=True, methods=["patch", "post"], url_path="status")
    @transaction.atomic
    def change_status(self, request, unique_id=None):
        ticket = self.get_object()
        status_code = request.data.get("status_code") or request.data.get("to_status_code")
        if not status_code:
            return Response({"status_code": "This field is required."}, status=http_status.HTTP_400_BAD_REQUEST)

        new_status = _resolve_status(status_code)
        if not new_status:
            return Response({"status_code": f"Unknown status '{status_code}'."}, status=http_status.HTTP_400_BAD_REQUEST)

        old_status = ticket.status
        ticket.status = new_status
        if new_status.status_code == "RESOLVED" and not ticket.resolved_at:
            ticket.resolved_at = timezone.now()
        if new_status.status_code == "CLOSED" and not ticket.closed_at:
            ticket.closed_at = timezone.now()
        ticket.save(update_fields=["status", "resolved_at", "closed_at"])

        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=old_status,
            to_status=new_status,
            changed_by_user=_actor_user(request),
            remarks=request.data.get("remarks"),
        )
        if new_status.status_code in CLOSED_STATUS_CODES:
            self._finalize_and_backfill(ticket)
        return Response(self.get_serializer(ticket).data)

    # ---- POST /tickets/{id}/resolve/ ----
    @action(detail=True, methods=["post"], url_path="resolve")
    @transaction.atomic
    def resolve(self, request, unique_id=None):
        ticket = self.get_object()
        resolved_status = _resolve_status("RESOLVED")
        if not resolved_status:
            return Response({"detail": "RESOLVED status not configured."}, status=http_status.HTTP_400_BAD_REQUEST)

        note = request.data.get("resolution_note") or request.data.get("remarks")
        old_status = ticket.status
        ticket.status = resolved_status
        if not ticket.resolved_at:
            ticket.resolved_at = timezone.now()
        ticket.save(update_fields=["status", "resolved_at"])

        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=old_status,
            to_status=resolved_status,
            changed_by_user=_actor_user(request),
            remarks=note or "Marked as resolved",
            visible_to_citizen=True,
        )
        if note:
            ComplaintComment.objects.create(
                ticket=ticket,
                comment_by_user=_actor_user(request),
                comment_text=note,
                is_internal=False,
            )
        self._finalize_and_backfill(ticket)
        return Response(self.get_serializer(ticket).data)

    # ---- POST /tickets/{id}/escalate/ ----
    @action(detail=True, methods=["post"], url_path="escalate")
    @transaction.atomic
    def escalate(self, request, unique_id=None):
        ticket = self.get_object()
        try:
            perform_escalation(
                ticket,
                reason=request.data.get("reason"),
                actor_user=_actor_user(request),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)

        ticket.refresh_from_db()
        return Response(self.get_serializer(ticket).data)

    # ---- POST /tickets/{id}/comments/ ----
    @action(detail=True, methods=["post"], url_path="comments")
    def add_comment(self, request, unique_id=None):
        ticket = self.get_object()
        comment = ComplaintComment.objects.create(
            ticket=ticket,
            comment_by_user=_actor_user(request),
            comment_text=request.data.get("comment_text", ""),
            is_internal=bool(request.data.get("is_internal", False)),
            is_sensitive=bool(request.data.get("is_sensitive", False)),
        )
        return Response(ComplaintCommentSerializer(comment).data, status=http_status.HTTP_201_CREATED)

    # ---- POST /tickets/{id}/attachments/ ----
    @action(detail=True, methods=["post"], url_path="attachments")
    def add_attachment(self, request, unique_id=None):
        ticket = self.get_object()
        attachment = ComplaintAttachment.objects.create(
            ticket=ticket,
            uploaded_by_user=_actor_user(request),
            file=request.data.get("file"),
            file_name=request.data.get("file_name"),
            file_type=request.data.get("file_type"),
            mime_type=request.data.get("mime_type"),
        )
        return Response(
            ComplaintAttachmentSerializer(attachment, context={"request": request}).data,
            status=http_status.HTTP_201_CREATED,
        )

    # ---- POST /tickets/{id}/reopen/ ----
    @action(detail=True, methods=["post"], url_path="reopen")
    @transaction.atomic
    def reopen(self, request, unique_id=None):
        ticket = self.get_object()
        if not ticket.status.allow_reopen:
            return Response(
                {"detail": "Current status does not allow reopen."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        reopened_status = _resolve_status("REOPENED")
        if not reopened_status:
            return Response({"detail": "REOPENED status not configured."}, status=http_status.HTTP_400_BAD_REQUEST)

        reopen_reason = request.data.get("reopen_reason")
        previous_status = ticket.status
        ticket.status = reopened_status
        ticket.reopened_count = (ticket.reopened_count or 0) + 1
        ticket.resolved_at = None
        ticket.closed_at = None
        ticket.save(update_fields=["status", "reopened_count", "resolved_at", "closed_at"])

        ComplaintReopenHistory.objects.create(
            ticket=ticket,
            reopened_by_user=_actor_user(request),
            reopen_reason=reopen_reason,
            previous_status=previous_status,
        )
        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=previous_status,
            to_status=reopened_status,
            changed_by_user=_actor_user(request),
            remarks=reopen_reason or "Reopened",
        )
        return Response(self.get_serializer(ticket).data)

    # ---- POST /tickets/{id}/feedback/ ----
    @action(detail=True, methods=["post"], url_path="feedback")
    def submit_feedback(self, request, unique_id=None):
        ticket = self.get_object()
        feedback, _ = ComplaintFeedback.objects.update_or_create(
            ticket=ticket,
            defaults={
                "customer": ticket.customer,
                "rating": request.data.get("rating"),
                "feedback_text": request.data.get("feedback_text"),
                "is_issue_solved": bool(request.data.get("is_issue_solved", False)),
            },
        )
        return Response(ComplaintFeedbackSerializer(feedback).data, status=http_status.HTTP_201_CREATED)
