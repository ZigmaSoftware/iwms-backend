from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import status as http_status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.complaint_management import (
    ComplaintAddressChangeRequest,
    ComplaintStatus,
    ComplaintStatusHistory,
)
from app.models.schedule_masters.trip_plan import TripPlan
from app.serializers.core_modules.complaint_management.ticket_serializers import (
    ComplaintAddressChangeRequestSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin

User = get_user_model()

GEO_FIELD_MAP = (
    ("state", "new_state"),
    ("district", "new_district"),
    ("panchayat_id", "new_panchayat"),
    ("zone", "new_zone"),
    ("ward", "new_ward"),
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
        "panchayat_id": customer.panchayat_id_id,
        "zone_id": customer.zone_id,
        "ward_id": customer.ward_id,
    }


class ComplaintAddressChangeViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ComplaintAddressChangeRequestSerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "address-change"

    def get_queryset(self):
        qs = ComplaintAddressChangeRequest.objects.filter(is_deleted=False).select_related(
            "ticket", "customer"
        ).order_by("-created")
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
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])
        return Response({"message": "Request deleted successfully"}, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, unique_id=None):
        req = self.get_object()
        req.verification_status = ComplaintAddressChangeRequest.VerificationStatus.VERIFIED
        req.verified_by = _actor_user(request)
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

        req.approved_by = _actor_user(request)
        req.approved_at = timezone.now()
        req.save()

        ticket = req.ticket
        resolved = _resolve_status("RESOLVED")
        route_warning = None
        if resolved:
            old_status = ticket.status
            ticket.status = resolved
            ticket.resolved_at = timezone.now()
            ticket.save(update_fields=["status", "resolved_at"])
            ComplaintStatusHistory.objects.create(
                ticket=ticket,
                from_status=old_status,
                to_status=resolved,
                changed_by_user=_actor_user(request),
                remarks="Address change approved",
            )

        if any(new_geo_fields.values()):
            covered = False
            coverage_checks = (
                ("ward", new_geo_fields.get("ward"), lambda value: TripPlan.objects.filter(wards__unique_id=value)),
                ("zone", new_geo_fields.get("zone"), lambda value: TripPlan.objects.filter(zone_id=value)),
                ("panchayat", new_geo_fields.get("panchayat_id"), lambda value: TripPlan.objects.filter(panchayat_id=value)),
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

        ticket = req.ticket
        rejected = _resolve_status("REJECTED")
        if rejected:
            old_status = ticket.status
            ticket.status = rejected
            ticket.save(update_fields=["status"])
            ComplaintStatusHistory.objects.create(
                ticket=ticket,
                from_status=old_status,
                to_status=rejected,
                changed_by_user=_actor_user(request),
                remarks=f"Address change rejected: {req.rejection_reason or ''}",
            )
        return Response(self.get_serializer(req).data)
