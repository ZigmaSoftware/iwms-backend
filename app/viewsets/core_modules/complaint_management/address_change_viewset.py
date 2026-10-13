from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status as http_status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.core_modules.complaint_management import (
    ComplaintAddressChangeRequest,
    ComplaintStatus,
    ComplaintStatusHistory,
)
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.serializers.core_modules.complaint_management.ticket_serializers import (
    ComplaintAddressChangeRequestSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin

User = get_user_model()

GEO_FIELD_MAP = (
    ("state", "new_state"),
    ("district", "new_district"),
    ("panchayat", "new_panchayat"),
    ("zone", "new_zone"),
    ("ward", "new_ward"),
)


def _ward_ids_contains(ward_id):
    """TripPlan.ward_ids is a comma-separated list of ward unique_ids."""
    return (
        Q(ward_ids=ward_id)
        | Q(ward_ids__startswith=f"{ward_id},")
        | Q(ward_ids__endswith=f",{ward_id}")
        | Q(ward_ids__contains=f",{ward_id},")
    )


def _move_ticket_status(ticket, new_status, request, remarks):
    """Set `ticket`'s status and record the transition. `ticket` can be None
    (the request's ticket_id may be blank)."""
    if not ticket or not new_status:
        return
    old_status_id = ticket.status_id
    ticket.status_id = new_status.unique_id
    update_fields = ["status_id"]
    if new_status.status_code == "RESOLVED":
        ticket.resolved_at = timezone.now()
        update_fields.append("resolved_at")
    ticket.save(update_fields=update_fields)
    ComplaintStatusHistory.objects.create(
        ticket_id=ticket.unique_id,
        from_status_id=old_status_id,
        to_status_id=new_status.unique_id,
        changed_by_user_id=getattr(_actor_user(request), "unique_id", None),
        remarks=remarks,
    )


def _actor_user(request):
    user = getattr(request, "user", None)
    return user if isinstance(user, User) else None


def _resolve_status(status_code):
    return ComplaintStatus.objects.filter(status_code=status_code, is_deleted=False).first()


def _snapshot_customer_address(customer):
    return {
        "building_no": customer.building_no,
        "street": customer.street,
        "area": customer.area,
        "pincode": customer.pincode,
        "latitude": customer.latitude,
        "longitude": customer.longitude,
        "state_id": customer.state_id,
        "district_id": customer.district_id,
        "panchayat_id": customer.panchayat_id,
        "zone_id": customer.zone_id,
        "ward_id": customer.ward_id,
    }


class ComplaintAddressChangeViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ComplaintAddressChangeRequestSerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "address-change"

    def get_queryset(self):
        qs = ComplaintAddressChangeRequest.objects.filter(is_deleted=False).order_by("-created")
        ticket = self.request.query_params.get("ticket")
        if ticket:
            qs = qs.filter(ticket_id=ticket)
        return qs

    def perform_create(self, serializer):
        instance = serializer.save()
        if instance.customer and not instance.old_address_snapshot:
            instance.old_address_snapshot = _snapshot_customer_address(instance.customer)
            instance.save(update_fields=["old_address_snapshot"])
        new_data = self._serialize_instance(instance)
        self.log_audit(self.request, instance=instance, previous_data=None, new_data=new_data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": "Request deleted successfully"}, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, unique_id=None):
        req = self.get_object()
        req.verification_status = ComplaintAddressChangeRequest.VerificationStatus.VERIFIED
        req.verified_by = getattr(_actor_user(request), "unique_id", None)
        req.verified_at = timezone.now()
        req.verification_remarks = request.data.get("verification_remarks")
        req.save(update_fields=["verification_status", "verified_by", "verified_at", "verification_remarks"])
        return Response(self.get_serializer(req).data)

    @action(detail=True, methods=["post"], url_path="approve")
    @transaction.atomic
    def approve(self, request, unique_id=None):
        req = self.get_object()
        customer = req.customer
        if not customer:
            return Response({"detail": "No customer linked to this request."}, status=http_status.HTTP_400_BAD_REQUEST)

        if not req.old_address_snapshot:
            req.old_address_snapshot = _snapshot_customer_address(customer)

        for customer_field, request_field in (
            ("building_no", "new_building_no"),
            ("street", "new_street"),
            ("area", "new_area"),
            ("pincode", "new_pincode"),
            ("latitude", "new_latitude"),
            ("longitude", "new_longitude"),
        ):
            value = getattr(req, request_field)
            if value is not None:
                setattr(customer, customer_field, value)

        new_geo_fields = {
            customer_field: getattr(req, f"{request_field}_id", None)
            for customer_field, request_field in GEO_FIELD_MAP
        }
        for customer_field, value in new_geo_fields.items():
            if value:
                setattr(customer, f"{customer_field}_id", value)
        customer.save()

        req.approved_by = getattr(_actor_user(request), "unique_id", None)
        req.approved_at = timezone.now()
        req.save()

        route_warning = None
        _move_ticket_status(req.ticket, _resolve_status("RESOLVED"), request, "Address change approved")

        if any(new_geo_fields.values()):
            covered = False
            coverage_checks = (
                ("ward", new_geo_fields.get("ward"), lambda value: TripPlan.objects.filter(_ward_ids_contains(value))),
                ("zone", new_geo_fields.get("zone"), lambda value: TripPlan.objects.filter(zone_id=value)),
                ("panchayat", new_geo_fields.get("panchayat"), lambda value: TripPlan.objects.filter(panchayat_id=value)),
                ("district", new_geo_fields.get("district"), lambda value: TripPlan.objects.filter(district_id=value)),
            )
            for _field, value, build_qs in coverage_checks:
                if value and build_qs(value).filter(is_deleted=False).exists():
                    covered = True
                    break
            if not covered:
                route_warning = "New location is not covered by any active TripPlan - manual route reassignment required."

        data = self.get_serializer(req).data
        if route_warning:
            data["route_warning"] = route_warning
        return Response(data)

    @action(detail=True, methods=["post"], url_path="reject")
    @transaction.atomic
    def reject(self, request, unique_id=None):
        req = self.get_object()
        req.verification_status = ComplaintAddressChangeRequest.VerificationStatus.REJECTED
        req.rejection_reason = request.data.get("rejection_reason")
        req.save(update_fields=["verification_status", "rejection_reason"])

        _move_ticket_status(
            req.ticket,
            _resolve_status("REJECTED"),
            request,
            f"Address change rejected: {req.rejection_reason or ''}",
        )
        return Response(self.get_serializer(req).data)
