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
    ComplaintAssignmentHistory,
    ComplaintAttachment,
    ComplaintComment,
    ComplaintDepartmentMember,
    ComplaintFeedback,
    ComplaintReopenHistory,
    ComplaintStatus,
    ComplaintStatusHistory,
    ComplaintTicket,
)
from app.models.notifications.staff_notification import StaffNotification
from app.models.staff_creations.department import Department
from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
from app.serializers.core_modules.complaint_management.ticket_serializers import (
    ComplaintAttachmentSerializer,
    ComplaintCommentSerializer,
    ComplaintFeedbackSerializer,
    ComplaintTicketDetailSerializer,
    ComplaintTicketSerializer,
)
from app.services.complaint_ticket_routing import (
    CLOSED_STATUS_CODES,
    _pick_least_loaded_staff,
    apply_routing_and_sla,
    backfill_department_queue,
    perform_escalation,
)
from app.services.staff_notification_service import notify_staff
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


def _has_supervisor_role(user):
    if getattr(user, "is_superuser", False) and getattr(user, "company_id", None) is None:
        return True
    role_obj = getattr(user, "staffusertype_id", None)
    role_name = (getattr(role_obj, "name", "") or "").lower()
    # Roles are stored with a tenant prefix ("Company Supervisor",
    # "Company Admin", "Company Project Admin"), so an equality test against
    # the bare word never matched and every supervisor silently fell through
    # to the per-staff scope below — which hid tickets that were not assigned
    # to them personally. Match on the significant word instead.
    return any(
        keyword in role_name
        for keyword in ("supervisor", "admin", "superadmin")
    )


def _supervised_department_ids(user):
    """Department ids where `user` is the active roster supervisor."""
    staff_id = getattr(user, "staff_unique_id", None)
    if not staff_id:
        return []
    return list(
        ComplaintDepartmentMember.objects.filter(
            staff_id=staff_id, is_supervisor=True, is_active=True, is_deleted=False,
        ).values_list("department_id", flat=True)
    )


def _is_department_supervisor(user):
    return bool(_supervised_department_ids(user))


def _staff_ticket_scope(user):
    """Tickets explicitly owned by a staff member, escalated to them, or
    (for a department supervisor) anywhere in a department they supervise."""
    scope = models.Q(assigned_staff=user) | models.Q(escalated_to_staff=user)
    supervised_departments = _supervised_department_ids(user)
    if supervised_departments:
        scope |= models.Q(department_id__in=supervised_departments)
    zone = getattr(user, "zone_id", None)
    if zone:
        scope |= models.Q(zone=zone)
    ward = getattr(user, "ward_id", None)
    if ward:
        scope |= models.Q(ward=ward)
    return scope


class ComplaintTicketViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    serializer_class = ComplaintTicketSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["ticket_no", "wa_phone", "profile_name", "title", "description", "customer__customer_name"]
    ordering_fields = ["created", "updated", "sla_due_at", "ticket_no"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "tickets"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ComplaintTicketDetailSerializer
        return ComplaintTicketSerializer

    def get_queryset(self):
        qs = ComplaintTicket.objects.filter(is_deleted=False).select_related(
            "category", "subcategory", "priority", "status", "source",
            "customer", "assigned_staff", "department", "escalated_to_staff",
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
            department = params.get("department")
            if department:
                qs = qs.filter(department_id=department)
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

        # Per-staff scoping: a regular staff member only sees tickets that
        # belong to them (assigned personally, to a team they lead, to their
        # department, or in their zone/ward). Supervisors/admins/superadmins
        # see everything CompanyScopedViewSet.filter_queryset already scopes
        # to their company/project.
        user = getattr(self.request, "user", None)
        is_staff_record = hasattr(user, "staff_unique_id")
        wants_all = params.get("all") in ("1", "true", "True")
        if is_staff_record and not wants_all and not (_has_supervisor_role(user) or _is_department_supervisor(user)):
            qs = qs.filter(_staff_ticket_scope(user))
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

        Clears any escalation flag (a closed ticket has nothing left to
        escalate) and, for a department-routed ticket, immediately hands the
        oldest queued unassigned ticket in that department to whichever
        member the resolution just freed up — the "real-time" backfill that
        keeps a member's queue topped up without a ticket sitting idle.
        """
        if ticket.is_escalated:
            ticket.is_escalated = False
            ticket.escalated_to_staff = None
            ticket.save(update_fields=["is_escalated", "escalated_to_staff"])
        if ticket.department_id:
            backfill_department_queue(ticket.department_id)

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

        previous_status = ticket.status
        ticket.status = reopened_status
        ticket.reopened_count = (ticket.reopened_count or 0) + 1
        ticket.resolved_at = None
        ticket.closed_at = None
        ticket.save(update_fields=["status", "reopened_count", "resolved_at", "closed_at"])

        ComplaintReopenHistory.objects.create(
            ticket=ticket,
            reopened_by_user=_actor_user(request),
            reopen_reason=request.data.get("reopen_reason"),
            previous_status=previous_status,
        )
        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=previous_status,
            to_status=reopened_status,
            changed_by_user=_actor_user(request),
            remarks="Reopened",
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

    # ---- POST /tickets/{id}/assign/ ----
    @action(detail=True, methods=["post"], url_path="assign")
    @transaction.atomic
    def assign(self, request, unique_id=None):
        ticket = self.get_object()
        department_id = request.data.get("department")
        staff_id = request.data.get("staff")

        from_staff = ticket.assigned_staff
        new_department = ticket.department

        if department_id:
            new_department = Department.objects.filter(unique_id=department_id, is_deleted=False).first()
            if not new_department:
                return Response({"department": "Invalid department."}, status=http_status.HTTP_400_BAD_REQUEST)

        # Resolve target staff: explicit staff param, else auto-pick the
        # least-loaded member of the (possibly just-changed) department,
        # else leave unchanged.
        new_staff = from_staff
        if staff_id:
            new_staff = StaffcreationOfficeDetails.objects.filter(staff_unique_id=staff_id).first()
            if not new_staff:
                return Response({"staff": "Invalid staff."}, status=http_status.HTTP_400_BAD_REQUEST)
        elif department_id and new_department:
            new_staff = _pick_least_loaded_staff(new_department)

        ticket.department = new_department
        ticket.assigned_staff = new_staff
        ticket.save(update_fields=["department", "assigned_staff"])

        ComplaintAssignmentHistory.objects.create(
            ticket=ticket,
            from_staff=from_staff,
            to_staff=new_staff,
            assigned_by=_actor_user(request),
            assignment_reason=request.data.get("reason"),
        )
        if new_staff and (not from_staff or new_staff.staff_unique_id != from_staff.staff_unique_id):
            notify_staff(
                new_staff,
                StaffNotification.TYPE_TICKET_ESCALATED_TO,
                "Ticket assigned to you",
                f"Ticket {ticket.ticket_no} ({ticket.title or ticket.category.category_name}) has been assigned to you.",
                data={"event": "ticket_assigned", "ticket_id": str(ticket.unique_id)},
            )
        return Response(self.get_serializer(ticket).data)

    # ---- GET /tickets/{id}/assignable-staff/ ----
    @action(detail=True, methods=["get"], url_path="assignable-staff")
    def assignable_staff(self, request, unique_id=None):
        """Department roster options for the Assign dialog, with each
        member's current open-ticket count so a supervisor can see load
        before assigning manually.

        Defaults to the ticket's own department; the caller may override
        with `?department=<department id>` to browse a different roster.
        """
        ticket = self.get_object()
        params = request.query_params
        department_id = params.get("department") or ticket.department_id
        if not department_id:
            return Response({"department_id": None, "count": 0, "staff": []})

        qs = (
            ComplaintDepartmentMember.objects.filter(
                department_id=department_id, is_supervisor=False, is_active=True, is_deleted=False,
            )
            .select_related("staff")
            .annotate(
                open_count=models.Count(
                    "staff__assigned_complaint_tickets_staff",
                    filter=~models.Q(
                        staff__assigned_complaint_tickets_staff__status__status_code__in=CLOSED_STATUS_CODES
                    )
                    & models.Q(staff__assigned_complaint_tickets_staff__is_deleted=False),
                    distinct=True,
                )
            )
            .order_by("open_count", "staff__employee_name")
        )

        return Response({
            "department_id": department_id,
            "count": qs.count(),
            "staff": [
                {
                    "staff_unique_id": m.staff.staff_unique_id,
                    "employee_name": m.staff.employee_name,
                    "open_ticket_count": m.open_count,
                }
                for m in qs
            ],
        })
