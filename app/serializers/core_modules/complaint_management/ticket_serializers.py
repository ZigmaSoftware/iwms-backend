"""Serializers for the ticketed complaint workflow.

Ported from the government backend's
`serializers/core_modules/complaint_management/transaction_serializers.py`.
Geo output follows this project's model (zone/ward/panchayat) instead of
government's AreaType + local-body hierarchy, and the government
`waste_types` M2M has no equivalent on this ticket, so those fields are
absent here.
"""

from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from app.models.customers.customercreation import CustomerCreation
from app.models.complaint_management import (
    ComplaintAddressChangeRequest,
    ComplaintAssignmentHistory,
    ComplaintAttachment,
    ComplaintComment,
    ComplaintEscalationHistory,
    ComplaintFeedback,
    ComplaintNotification,
    ComplaintPriority,
    ComplaintReopenHistory,
    ComplaintRoutingRule,
    ComplaintStatus,
    ComplaintStatusHistory,
    ComplaintTicket,
    ComplaintTicketExtraDetail,
)


class ComplaintTicketSerializer(serializers.ModelSerializer):
    OPERATIONAL_CONTEXT_FIELDS = (
        "incident_type",
        "trip_reference",
        "driver_reference",
        "operator_reference",
        "vehicle_reference",
        "other_reference",
    )

    module = serializers.CharField(source="category.module_id", read_only=True)
    module_code = serializers.CharField(source="category.module.module_code", read_only=True)
    module_name = serializers.CharField(source="category.module.module_name", read_only=True)
    category_name = serializers.CharField(source="category.category_name", read_only=True)
    category_code = serializers.CharField(source="category.category_code", read_only=True)
    subcategory_name = serializers.CharField(source="subcategory.subcategory_name", read_only=True)
    priority_code = serializers.CharField(source="priority.priority_code", read_only=True)
    priority_name = serializers.CharField(source="priority.priority_name", read_only=True)
    status_code = serializers.CharField(source="status.status_code", read_only=True)
    status_name = serializers.CharField(source="status.status_name", read_only=True)
    source_code = serializers.CharField(source="source.source_code", read_only=True)
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    reporter_type = serializers.SerializerMethodField()
    reporter_name = serializers.SerializerMethodField()
    assigned_team_name = serializers.CharField(source="assigned_team.team_name", read_only=True)
    assigned_staff_name = serializers.CharField(source="assigned_staff.employee_name", read_only=True)
    assigned_department_name = serializers.CharField(
        source="assigned_team.department.department_name", read_only=True
    )
    escalation_level = serializers.IntegerField(source="assigned_team.escalation_level", read_only=True)

    state_name = serializers.CharField(source="state.name", read_only=True)
    district_name = serializers.CharField(source="district.name", read_only=True)
    panchayat_name = serializers.CharField(source="panchayat.panchayat_name", read_only=True)
    zone_name = serializers.CharField(source="zone.zone_name", read_only=True)
    ward_name = serializers.CharField(source="ward.ward_name", read_only=True)

    sla_time_remaining_seconds = serializers.SerializerMethodField()
    public_timeline = serializers.SerializerMethodField()
    # The app reads the citizen-facing history under `timeline`; keep both so
    # the admin screens that expect `public_timeline` keep working.
    timeline = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    close_image_url = serializers.SerializerMethodField()
    operational_context = serializers.SerializerMethodField()

    incident_type = serializers.CharField(write_only=True, required=False, allow_blank=True)
    trip_reference = serializers.CharField(write_only=True, required=False, allow_blank=True)
    driver_reference = serializers.CharField(write_only=True, required=False, allow_blank=True)
    operator_reference = serializers.CharField(write_only=True, required=False, allow_blank=True)
    vehicle_reference = serializers.CharField(write_only=True, required=False, allow_blank=True)
    other_reference = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = ComplaintTicket
        fields = "__all__"
        read_only_fields = [
            "unique_id", "ticket_no", "resolved_at", "closed_at", "reopened_count",
            "sla_breached", "sla_breached_at",
        ]
        # Derived in `_apply_derived_defaults` when omitted, so the staff form
        # need not ask for them. Still accepted if a caller sends one.
        extra_kwargs = {
            "priority": {"required": False},
            "status": {"required": False},
        }

    def get_reporter_type(self, obj):
        return "Customer" if obj.customer_id or self._matched_customer_name(obj) else "Public Grievance"

    def get_reporter_name(self, obj):
        return (
            getattr(obj.customer, "customer_name", "")
            or (obj.profile_name or "").strip()
            or self._matched_customer_name(obj)
            or "Anonymous"
        )

    def _matched_customer_name(self, obj):
        phone = (obj.wa_phone or "").strip()
        email = (obj.email or "").strip()
        if not phone and not email:
            return ""
        cache = getattr(self, "_customer_identity_cache", {})
        cache_key = (phone, email.lower())
        if cache_key not in cache:
            identity_filter = Q()
            if phone:
                identity_filter |= Q(contact_no=phone)
            if email:
                identity_filter |= Q(email__iexact=email)
            cache[cache_key] = (
                CustomerCreation.objects.filter(identity_filter, is_deleted=False)
                .values_list("customer_name", flat=True)
                .first()
                or ""
            )
            self._customer_identity_cache = cache
        return cache[cache_key]

    def _pop_operational_context(self, validated_data):
        return {
            field: validated_data.pop(field, "")
            for field in self.OPERATIONAL_CONTEXT_FIELDS
            if field in validated_data
        }

    def _save_operational_context(self, ticket, values):
        for field, value in values.items():
            cleaned = str(value or "").strip()
            row = ComplaintTicketExtraDetail.objects.filter(
                ticket=ticket,
                field_key=field,
                is_deleted=False,
            ).first()
            if cleaned:
                ComplaintTicketExtraDetail.objects.update_or_create(
                    ticket=ticket,
                    field_key=field,
                    is_deleted=False,
                    defaults={
                        "field_value": cleaned,
                        "field_type": "operational_context",
                        "is_active": True,
                    },
                )
            elif row:
                row.is_deleted = True
                row.is_active = False
                row.save(update_fields=["is_deleted", "is_active"])

    def _apply_derived_defaults(self, validated_data):
        """Fill priority/status when the caller did not send them.

        Both are non-null `PROTECT` FKs on the model, but neither is a
        decision the person raising a ticket should have to make: priority
        comes from the chosen subcategory or category (the same precedence
        `PublicGrievanceViewSet` uses), and a new ticket is always SUBMITTED.
        Leaving them out of the staff form removes two required pickers whose
        answer is already implied by the category.
        """
        if not validated_data.get("priority"):
            subcategory = validated_data.get("subcategory")
            category = validated_data.get("category")
            validated_data["priority"] = (
                getattr(subcategory, "default_priority", None)
                or getattr(category, "default_priority", None)
                or ComplaintPriority.objects.filter(
                    priority_code="P3", is_deleted=False
                ).first()
            )
        if not validated_data.get("status"):
            validated_data["status"] = ComplaintStatus.objects.filter(
                status_code="SUBMITTED", is_deleted=False
            ).first()
        return validated_data

    def create(self, validated_data):
        context = self._pop_operational_context(validated_data)
        validated_data = self._apply_derived_defaults(validated_data)
        ticket = super().create(validated_data)
        self._save_operational_context(ticket, context)
        return ticket

    def update(self, instance, validated_data):
        context = self._pop_operational_context(validated_data)
        ticket = super().update(instance, validated_data)
        self._save_operational_context(ticket, context)
        return ticket

    def get_operational_context(self, obj):
        values = {
            row.field_key: row.field_value
            for row in obj.extra_details.all()
            if not row.is_deleted and row.field_key in self.OPERATIONAL_CONTEXT_FIELDS
        }
        incident_type = (values.get("incident_type") or "").strip().lower()
        if not incident_type:
            source_code = (getattr(obj.source, "source_code", "") or "").lower()
            searchable = " ".join(
                str(value or "").lower()
                for value in (
                    obj.title,
                    obj.description,
                    getattr(obj.category, "category_name", ""),
                    getattr(obj.subcategory, "subcategory_name", ""),
                    getattr(getattr(obj.category, "module", None), "module_name", ""),
                )
            )
            if source_code == "public_grievance":
                incident_type = "public"
            else:
                incident_type = next(
                    (
                        kind
                        for kind in ("driver", "operator", "vehicle", "trip")
                        if kind in searchable
                    ),
                    "other",
                )
        return {
            "incident_type": incident_type,
            "trip_reference": values.get("trip_reference") or "",
            "driver_reference": values.get("driver_reference") or "",
            "operator_reference": values.get("operator_reference") or "",
            "vehicle_reference": values.get("vehicle_reference") or "",
            "other_reference": values.get("other_reference") or "",
        }

    def _active_attachments(self, obj):
        """Attachments ordered newest-first (model default ordering)."""
        return [a for a in obj.attachments.all() if not a.is_deleted]

    def get_image_url(self, obj):
        """URL of the original complaint photo (oldest attachment)."""
        request = self.context.get("request")
        attachments = self._active_attachments(obj)
        if not attachments or not request:
            return None
        oldest = attachments[-1]
        return request.build_absolute_uri(oldest.file.url) if oldest.file else None

    def get_close_image_url(self, obj):
        """URL of the resolution photo (most recent attachment, if a later one was added)."""
        request = self.context.get("request")
        attachments = self._active_attachments(obj)
        if len(attachments) < 2 or not request:
            return None
        newest = attachments[0]
        return request.build_absolute_uri(newest.file.url) if newest.file else None

    def get_sla_time_remaining_seconds(self, obj):
        """Seconds until sla_due_at (negative once overdue); None if resolved/closed or no due date."""
        if not obj.sla_due_at or obj.resolved_at or obj.closed_at:
            return None
        return int((obj.sla_due_at - timezone.now()).total_seconds())

    def _citizen_timeline(self, obj):
        rows = [
            h for h in obj.status_history.all()
            if h.visible_to_citizen and not h.is_deleted
        ]
        rows.sort(key=lambda h: h.changed_at)
        return [
            {
                "status_code": h.to_status.status_code if h.to_status_id else None,
                "status_name": h.to_status.status_name if h.to_status_id else None,
                "status": h.to_status.status_name if h.to_status_id else None,
                "at": h.changed_at,
                "remarks": h.remarks,
            }
            for h in rows
        ]

    def get_public_timeline(self, obj):
        """Citizen-safe, chronological status timeline (visible_to_citizen only)."""
        return self._citizen_timeline(obj)

    def get_timeline(self, obj):
        return self._citizen_timeline(obj)


class ComplaintTicketExtraDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintTicketExtraDetail
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ComplaintAttachment
        fields = "__all__"
        read_only_fields = ["unique_id"]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None


class ComplaintStatusHistorySerializer(serializers.ModelSerializer):
    from_status_code = serializers.CharField(source="from_status.status_code", read_only=True)
    to_status_code = serializers.CharField(source="to_status.status_code", read_only=True)
    to_status_name = serializers.CharField(source="to_status.status_name", read_only=True)

    class Meta:
        model = ComplaintStatusHistory
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintAssignmentHistorySerializer(serializers.ModelSerializer):
    to_team_name = serializers.CharField(source="to_team.team_name", read_only=True)
    from_team_name = serializers.CharField(source="from_team.team_name", read_only=True)
    to_staff_name = serializers.CharField(source="to_staff.employee_name", read_only=True)
    from_staff_name = serializers.CharField(source="from_staff.employee_name", read_only=True)

    class Meta:
        model = ComplaintAssignmentHistory
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintComment
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintRoutingRuleSerializer(serializers.ModelSerializer):
    category_code = serializers.CharField(source="category.category_code", read_only=True)
    team_name = serializers.CharField(source="team.team_name", read_only=True)

    class Meta:
        model = ComplaintRoutingRule
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintEscalationHistorySerializer(serializers.ModelSerializer):
    escalated_from_team_name = serializers.CharField(source="escalated_from_team.team_name", read_only=True)
    escalated_to_team_name = serializers.CharField(source="escalated_to_team.team_name", read_only=True)
    escalated_to_staff_name = serializers.CharField(source="escalated_to_staff.employee_name", read_only=True)

    class Meta:
        model = ComplaintEscalationHistory
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintTicketDetailSerializer(ComplaintTicketSerializer):
    """Ticket retrieve view with the full audit trail nested (for the admin screen)."""

    status_history = ComplaintStatusHistorySerializer(many=True, read_only=True)
    escalation_history = ComplaintEscalationHistorySerializer(many=True, read_only=True)
    assignment_history = ComplaintAssignmentHistorySerializer(many=True, read_only=True)
    comments = ComplaintCommentSerializer(many=True, read_only=True)
    attachments = ComplaintAttachmentSerializer(many=True, read_only=True)

    class Meta(ComplaintTicketSerializer.Meta):
        pass


class ComplaintFeedbackSerializer(serializers.ModelSerializer):
    ticket_no = serializers.CharField(source="ticket.ticket_no", read_only=True)
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)

    class Meta:
        model = ComplaintFeedback
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintReopenHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintReopenHistory
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintNotificationSerializer(serializers.ModelSerializer):
    ticket_no = serializers.CharField(source="ticket.ticket_no", read_only=True)

    class Meta:
        model = ComplaintNotification
        fields = "__all__"
        read_only_fields = ["unique_id", "created_at"]


class ComplaintAddressChangeRequestSerializer(serializers.ModelSerializer):
    ticket_no = serializers.CharField(source="ticket.ticket_no", read_only=True)
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    proof_file_url = serializers.SerializerMethodField()

    class Meta:
        model = ComplaintAddressChangeRequest
        fields = "__all__"
        read_only_fields = [
            "unique_id",
            "verification_status",
            "verified_by",
            "verified_at",
            "approved_by",
            "approved_at",
        ]

    def get_proof_file_url(self, obj):
        request = self.context.get("request")
        if obj.proof_file and request:
            return request.build_absolute_uri(obj.proof_file.url)
        return None
