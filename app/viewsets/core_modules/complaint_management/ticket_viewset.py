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
    ComplaintFeedback,
    ComplaintReopenHistory,
    ComplaintStatus,
    ComplaintStatusHistory,
    ComplaintTeam,
    ComplaintTicket,
)
from app.models.notifications.staff_notification import StaffNotification
from app.models.user_creations.staffcreation import Staffcreation, StaffcreationOfficeDetails
from app.serializers.core_modules.complaint_management.ticket_serializers import (
    ComplaintAttachmentSerializer,
    ComplaintCommentSerializer,
    ComplaintFeedbackSerializer,
    ComplaintTicketDetailSerializer,
    ComplaintTicketSerializer,
)
from app.services.staff_notification_service import notify_staff
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet

User = get_user_model()


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
        return models.Q(status__status_code__in=["RESOLVED", "CLOSED", "REJECTED", "CANCELLED"])
    if bucket == "open":
        return ~models.Q(status__status_code__in=["RESOLVED", "CLOSED", "REJECTED", "CANCELLED"])
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


def _staff_ticket_scope(user):
    """Tickets explicitly owned by a staff member or their team/department."""
    scope = models.Q(assigned_staff=user) | models.Q(assigned_team__lead_staff=user)
    department = getattr(user, "department_id", None)
    if department:
        scope |= models.Q(assigned_team__department=department)
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
            "customer", "assigned_team", "assigned_team__department",
            "assigned_staff", "state", "district", "panchayat", "zone", "ward",
        ).prefetch_related(
            "status_history", "status_history__to_status",
            "escalation_history", "escalation_history__escalated_to_team",
            "escalation_history__escalated_from_team",
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
            zone = params.get("zone")
            if zone:
                qs = qs.filter(zone_id=zone)
            ward = params.get("ward")
            if ward:
                qs = qs.filter(ward_id=ward)
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
        if is_staff_record and not wants_all and not _has_supervisor_role(user):
            qs = qs.filter(_staff_ticket_scope(user))
        return qs

    @action(detail=False, methods=["get"], url_path="counts")
    def counts(self, request):
        qs = self.filter_queryset(self.get_queryset())
        total = qs.count()
        public = qs.filter(source__source_code="PUBLIC_GRIEVANCE").count()
        return Response({
            "all": total,
            "public": public,
            "internal": total - public,
        })

    def perform_create(self, serializer):
        super().perform_create(serializer)  # tenancy + audit (CompanyScopedViewSet)
        ticket = serializer.instance
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
        return Response(self.get_serializer(ticket).data)

    # ---- POST /tickets/{id}/escalate/ ----
    @action(detail=True, methods=["post"], url_path="escalate")
    @transaction.atomic
    def escalate(self, request, unique_id=None):
        ticket = self.get_object()
        team_id = request.data.get("team")
        target = None
        if team_id:
            target = ComplaintTeam.objects.filter(unique_id=team_id, is_deleted=False).first()
            if not target:
                return Response({"team": "Invalid team."}, status=http_status.HTTP_400_BAD_REQUEST)
        elif ticket.assigned_team_id:
            target = ComplaintTeam.objects.filter(
                unique_id=ticket.assigned_team.escalates_to_id, is_deleted=False
            ).first()
        if not target:
            return Response(
                {"detail": "No escalation target team configured for this ticket."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        escalated_status = _resolve_status("ESCALATED")
        old_status = ticket.status
        old_team = ticket.assigned_team
        ticket.assigned_team = target
        update_fields = ["assigned_team"]
        if escalated_status:
            ticket.status = escalated_status
            update_fields.append("status")
        ticket.save(update_fields=update_fields)

        from app.models.complaint_management import ComplaintAssignmentHistory, ComplaintEscalationHistory

        ComplaintAssignmentHistory.objects.create(
            ticket=ticket,
            from_team=old_team,
            to_team=target,
            assigned_by=_actor_user(request),
            assignment_reason=request.data.get("reason") or "Escalated",
        )
        ComplaintEscalationHistory.objects.create(
            ticket=ticket,
            escalation_level=(old_team.escalation_level if old_team else 0) + 1,
            escalated_from_team=old_team,
            escalated_to_team=target,
            escalated_to_user=_actor_user(request),
            reason=request.data.get("reason"),
        )
        if escalated_status and old_status.pk != escalated_status.pk:
            ComplaintStatusHistory.objects.create(
                ticket=ticket,
                from_status=old_status,
                to_status=escalated_status,
                changed_by_user=_actor_user(request),
                remarks="Escalated",
            )
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
        team_id = request.data.get("team")
        staff_id = request.data.get("staff")

        from_team = ticket.assigned_team
        from_staff = ticket.assigned_staff

        new_team = from_team
        if team_id:
            new_team = ComplaintTeam.objects.filter(unique_id=team_id, is_deleted=False).first()
            if not new_team:
                return Response({"team": "Invalid team."}, status=http_status.HTTP_400_BAD_REQUEST)

        # Resolve target staff: explicit staff param, else the team's lead, else unchanged.
        new_staff = from_staff
        if staff_id:
            new_staff = StaffcreationOfficeDetails.objects.filter(staff_unique_id=staff_id).first()
            if not new_staff:
                return Response({"staff": "Invalid staff."}, status=http_status.HTTP_400_BAD_REQUEST)
        elif team_id and new_team and new_team.lead_staff_id:
            new_staff = new_team.lead_staff

        ticket.assigned_team = new_team
        ticket.assigned_staff = new_staff
        ticket.save(update_fields=["assigned_team", "assigned_staff"])

        ComplaintAssignmentHistory.objects.create(
            ticket=ticket,
            from_team=from_team,
            to_team=new_team,
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
        """Staff options for the Assign dialog, scoped to a zone/ward.

        Defaults to the ticket's own zone/ward; the caller may override with
        `?zone=<zone id>` and/or `?ward=<ward id>` to browse a different area
        before assigning. A staff member tagged to the zone still shows up
        when the caller drills into one ward inside it (coarser scope
        matches finer scope, and vice versa).
        """
        ticket = self.get_object()
        params = request.query_params
        zone_id = params.get("zone") or ticket.zone_id
        ward_id = params.get("ward") or ticket.ward_id

        qs = Staffcreation.objects.filter(is_deleted=False, is_active=True)

        if zone_id or ward_id:
            scope = models.Q()
            if zone_id:
                scope |= models.Q(zone_id=zone_id)
            if ward_id:
                scope |= models.Q(ward_id=ward_id)
            qs = qs.filter(scope)

        role_name = params.get("role")
        if role_name:
            qs = qs.filter(staffusertype_id__name__icontains=role_name)

        qs = qs.select_related("staffusertype_id", "zone_id", "ward_id").order_by("employee_name")

        return Response([
            {
                "staff_unique_id": s.staff_unique_id,
                "employee_name": s.employee_name,
                "role": getattr(s.staffusertype_id, "name", None),
                "zone": getattr(s.zone_id, "zone_name", None),
                "ward": getattr(s.ward_id, "ward_name", None),
            }
            for s in qs
        ])
