"""Serializers for the ticketed complaint workflow.

Ported from the government backend's
`serializers/core_modules/complaint_management/transaction_serializers.py`.
Geo output follows this project's model (zone/ward/panchayat) instead of
government's AreaType + local-body hierarchy, and the government
`waste_types` M2M has no equivalent on this ticket, so those fields are
absent here.
"""

from django.db import models
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.superadmin.common_masters.state import State
from app.models.superadmin.role_management.projectStaffHierarchy import ProjectStaffHierarchy
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
from app.models.core_modules.complaint_management import (
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
from app.models.core_modules.complaint_management.masters import (
    ComplaintCategory,
    ComplaintModule,
    ComplaintSource,
    ComplaintSubcategory,
)
from app.utils.related_prefetch import prefetch_related_rows, related

TICKET_LOOKUPS = {
    "category": (ComplaintCategory, "category_id"),
    "subcategory": (ComplaintSubcategory, "subcategory_id"),
    "priority": (ComplaintPriority, "priority_id"),
    "status": (ComplaintStatus, "status_id"),
    "source": (ComplaintSource, "source_id"),
    "customer": (CustomerCreation, "customer_id"),
    "assigned_staff": (StaffcreationOfficeDetails, "assigned_staff_id", "staff_unique_id"),
    "escalated_to_staff": (StaffcreationOfficeDetails, "escalated_to_staff_id", "staff_unique_id"),
    "state": (State, "state_id"),
    "district": (District, "district_id"),
    "panchayat": (Panchayat, "panchayat_id"),
    "zone": (Zone, "zone_id"),
    "ward": (Ward, "ward_id"),
}
# Child rows the list renders per ticket, as (cache attr, model). Fetched
# unfiltered in model ordering, like the ticket's own properties.
TICKET_CHILDREN = {
    "extra_details": ComplaintTicketExtraDetail,
    "attachments": ComplaintAttachment,
    "status_history": ComplaintStatusHistory,
}


class _RelatedView:
    """Attribute view of a row that resolves relations through `related()`,
    so dotted `source=` paths hit the prefetched rows."""

    def __init__(self, obj):
        self._obj = obj

    def __getattr__(self, name):
        value = related(self._obj, name)
        return _RelatedView(value) if isinstance(value, models.Model) else value


class _RelatedCharField(serializers.CharField):
    def get_attribute(self, instance):
        return super().get_attribute(_RelatedView(instance))


def _children(obj, name):
    cached = getattr(obj, "_ticket_children", None)
    if cached is not None:
        return cached[name]
    return list(getattr(obj, name).all())


class ComplaintTicketListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        instances = list(data.all() if hasattr(data, "all") else data)
        rows = prefetch_related_rows(instances, TICKET_LOOKUPS)
        prefetch_related_rows(
            rows["category"].values(), {"module": (ComplaintModule, "module_id")}
        )

        ticket_ids = [obj.unique_id for obj in instances]
        children = {}
        for name, model in TICKET_CHILDREN.items():
            grouped = {}
            # Keep the query's row order.
            for row in model.objects.filter(ticket_id__in=ticket_ids):
                grouped.setdefault(row.ticket_id, []).append(row)
            children[name] = grouped
        prefetch_related_rows(
            [h for group in children["status_history"].values() for h in group],
            {"to_status": (ComplaintStatus, "to_status_id")},
        )

        # First non-deleted hierarchy row per (project, level), as
        # get_escalation_level_name's `.first()` would pick.
        hierarchy = {}
        project_ids = {obj.project_id for obj in instances if obj.project_id}
        if project_ids:
            for entry in ProjectStaffHierarchy.objects.filter(
                project_id__in=project_ids, is_deleted=False
            ):
                hierarchy.setdefault((entry.project_id, entry.level), entry)
            prefetch_related_rows(
                hierarchy.values(), {"staffusertype": (StaffUserType, "staffusertype_id")}
            )

        for obj in instances:
            obj._ticket_children = {
                name: grouped.get(obj.unique_id, []) for name, grouped in children.items()
            }
            obj._hierarchy_entry = hierarchy.get((obj.project_id, obj.escalation_level))
        self._prefill_customer_identities(instances)
        return super().to_representation(instances)

    def _prefill_customer_identities(self, instances):
        """Fill the child's `_matched_customer_name` cache with one query."""
        keys = {
            ((obj.wa_phone or "").strip(), (obj.email or "").strip().lower())
            for obj in instances
        }
        keys.discard(("", ""))
        if not keys:
            return
        identity_filter = Q()
        phones = {phone for phone, _ in keys if phone}
        if phones:
            identity_filter |= Q(contact_no__in=phones)
        for email in {email for _, email in keys if email}:
            identity_filter |= Q(email__iexact=email)
        qs = CustomerCreation.objects.filter(identity_filter, is_deleted=False)
        if not qs.ordered:
            qs = qs.order_by("pk")  # as `.first()` would
        candidates = list(qs.values_list("contact_no", "email", "customer_name"))

        def norm(value):
            return (value or "").rstrip().lower()

        cache = getattr(self.child, "_customer_identity_cache", {})
        for phone, email in keys:
            cache[(phone, email)] = next(
                (
                    name for contact_no, row_email, name in candidates
                    if (phone and norm(contact_no) == norm(phone))
                    or (email and norm(row_email) == email.rstrip())
                ),
                None,
            ) or ""
        self.child._customer_identity_cache = cache


class ComplaintTicketSerializer(serializers.ModelSerializer):
    OPERATIONAL_CONTEXT_FIELDS = (
        "incident_type",
        "trip_reference",
        "driver_reference",
        "operator_reference",
        "vehicle_reference",
        "other_reference",
    )

    module = _RelatedCharField(source="category.module_id", read_only=True)
    module_code = _RelatedCharField(source="category.module.module_code", read_only=True)
    module_name = _RelatedCharField(source="category.module.module_name", read_only=True)
    category_name = _RelatedCharField(source="category.category_name", read_only=True)
    category_code = _RelatedCharField(source="category.category_code", read_only=True)
    subcategory_name = _RelatedCharField(source="subcategory.subcategory_name", read_only=True)
    priority_code = _RelatedCharField(source="priority.priority_code", read_only=True)
    priority_name = _RelatedCharField(source="priority.priority_name", read_only=True)
    status_code = _RelatedCharField(source="status.status_code", read_only=True)
    status_name = _RelatedCharField(source="status.status_name", read_only=True)
    source_code = _RelatedCharField(source="source.source_code", read_only=True)
    customer_name = _RelatedCharField(source="customer.customer_name", read_only=True)
    reporter_type = serializers.SerializerMethodField()
    reporter_name = serializers.SerializerMethodField()
    assigned_staff_name = _RelatedCharField(source="assigned_staff.employee_name", read_only=True)
    escalated_to_staff_name = _RelatedCharField(source="escalated_to_staff.employee_name", read_only=True)

    state_name = _RelatedCharField(source="state.name", read_only=True)
    district_name = _RelatedCharField(source="district.name", read_only=True)
    panchayat_name = _RelatedCharField(source="panchayat.panchayat_name", read_only=True)
    zone_name = _RelatedCharField(source="zone.zone_name", read_only=True)
    ward_name = _RelatedCharField(source="ward.ward_name", read_only=True)

    sla_time_remaining_seconds = serializers.SerializerMethodField()
    escalation_level_name = serializers.SerializerMethodField()
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
        list_serializer_class = ComplaintTicketListSerializer
        read_only_fields = [
            "unique_id", "ticket_no", "resolved_at", "closed_at", "reopened_count",
        ]
        # Derived in `_apply_derived_defaults` when omitted, so the staff form
        # need not ask for them. Still accepted if a caller sends one.
        extra_kwargs = {
            "priority_id": {"required": False},
            "status_id": {"required": False},
        }

    # The ticket's references are `<name>_id` CharFields, but the staff
    # wizard (and older clients) post them under the relation name
    # (`category`, `status`, `ward`, ...). Accept either spelling so those
    # values aren't silently dropped by `fields = "__all__"`.
    RELATION_ALIASES = (
        "source", "customer", "language", "category", "subcategory",
        "priority", "status", "state", "district", "panchayat", "zone",
        "ward", "assigned_user", "assigned_staff", "escalated_to_staff",
        "parent_ticket",
    )

    def to_internal_value(self, data):
        # A plain dict rather than QueryDict.copy(), which deep-copies any
        # uploaded files on a multipart post.
        data = dict(data.items())
        for name in self.RELATION_ALIASES:
            id_field = f"{name}_id"
            if name in data and id_field not in data:
                value = data.get(name)
                if isinstance(value, dict):
                    value = value.get("unique_id")
                data[id_field] = value or None
        return super().to_internal_value(data)

    def get_reporter_type(self, obj):
        return "Customer" if obj.customer_id or self._matched_customer_name(obj) else "Internal"

    def get_reporter_name(self, obj):
        return (
            getattr(related(obj, "customer"), "customer_name", "")
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
                ticket_id=ticket.unique_id,
                field_key=field,
                is_deleted=False,
            ).first()
            if cleaned:
                ComplaintTicketExtraDetail.objects.update_or_create(
                    ticket_id=ticket.unique_id,
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

        Every ticket needs both, but neither is a
        decision the person raising a ticket should have to make: priority
        comes from the chosen subcategory or category, and a new ticket is
        always SUBMITTED.
        Leaving them out of the staff form removes two required pickers whose
        answer is already implied by the category.
        """
        if not validated_data.get("priority_id"):
            subcategory = ComplaintSubcategory.objects.filter(
                unique_id=validated_data.get("subcategory_id") or None
            ).first()
            category = ComplaintCategory.objects.filter(
                unique_id=validated_data.get("category_id") or None
            ).first()
            fallback = ComplaintPriority.objects.filter(
                priority_code="P3", is_deleted=False
            ).first()
            validated_data["priority_id"] = (
                getattr(subcategory, "default_priority_id", None)
                or getattr(category, "default_priority_id", None)
                or getattr(fallback, "unique_id", None)
            )
        if not validated_data.get("status_id"):
            submitted = ComplaintStatus.objects.filter(
                status_code="SUBMITTED", is_deleted=False
            ).first()
            validated_data["status_id"] = getattr(submitted, "unique_id", None)
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
            for row in _children(obj, "extra_details")
            if not row.is_deleted and row.field_key in self.OPERATIONAL_CONTEXT_FIELDS
        }
        incident_type = (values.get("incident_type") or "").strip().lower()
        if not incident_type:
            category = related(obj, "category")
            module = related(category, "module") if category else None
            searchable = " ".join(
                str(value or "").lower()
                for value in (
                    obj.title,
                    obj.description,
                    getattr(category, "category_name", ""),
                    getattr(related(obj, "subcategory"), "subcategory_name", ""),
                    getattr(module, "module_name", ""),
                )
            )
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
        return [a for a in _children(obj, "attachments") if not a.is_deleted]

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
        """Seconds until next_escalation_due_at (negative once overdue); None if
        resolved/closed, at the top of the hierarchy (no further deadline), or
        no due date."""
        if not obj.next_escalation_due_at or obj.resolved_at or obj.closed_at:
            return None
        return int((obj.next_escalation_due_at - timezone.now()).total_seconds())

    def get_escalation_level_name(self, obj):
        """Human role name (e.g. "Supervisor") for the ticket's current
        `escalation_level`, resolved from the project's staff hierarchy."""
        if not obj.project_id:
            return None
        if hasattr(obj, "_hierarchy_entry"):
            entry = obj._hierarchy_entry
        else:
            entry = ProjectStaffHierarchy.objects.filter(
                project_id=obj.project_id, level=obj.escalation_level, is_deleted=False,
            ).first()
        staffusertype = related(entry, "staffusertype") if entry else None
        return staffusertype.get_name_display() if staffusertype else None

    def _citizen_timeline(self, obj):
        rows = [
            h for h in _children(obj, "status_history")
            if h.visible_to_citizen and not h.is_deleted
        ]
        rows.sort(key=lambda h: h.changed_at)
        timeline = []
        for h in rows:
            to_status = related(h, "to_status") if h.to_status_id else None
            timeline.append({
                "status_code": to_status.status_code if h.to_status_id else None,
                "status_name": to_status.status_name if h.to_status_id else None,
                "status": to_status.status_name if h.to_status_id else None,
                "at": h.changed_at,
                "remarks": h.remarks,
            })
        return timeline

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

    class Meta:
        model = ComplaintRoutingRule
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintEscalationHistorySerializer(serializers.ModelSerializer):
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
