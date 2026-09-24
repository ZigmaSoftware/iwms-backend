from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.serializers.core_modules.daily_operations.bin_collection_event_serializer import (
    BinCollectionEventSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class BinCollectionEventViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    serializer_class = BinCollectionEventSerializer
    lookup_field = "unique_id"
    permission_resource = "BinCollectionEvent"
    filter_backends = [ModelFieldQueryFilter, ModelFieldSearchFilter, SerializerOrderingFilter]

    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "bin-collection-event"

    def get_queryset(self):
        # NOTE: no select_related() here — every *_id field on this model
        # (company_id, trip_assignment_id, bin_id, etc.) is this codebase's
        # plain "string-pseudo-FK" CharField, not a real Django relation, so
        # select_related() on any of them raises FieldError. Related rows are
        # resolved individually via the model's @property accessors instead
        # (see BinCollectionEvent.trip_assignment/.bin/etc. and the
        # serializer's get_* methods).
        queryset = BinCollectionEvent.objects.filter(is_deleted=False)

        params = self.request.query_params
        trip_assignment = params.get("trip_assignment_id")
        trip_collection_point = params.get("trip_collection_point_id")
        bin_id = params.get("bin_id")
        panchayat = params.get("panchayat_id")
        ward = params.get("ward_id")
        zone = params.get("zone_id")
        status_value = params.get("status")
        collection_date = params.get("collection_date") or params.get("date")
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        mine = params.get("mine")

        if mine and str(mine).lower() in ("1", "true", "yes"):
            # Supervisor app waste summary: events on trips whose plan this
            # supervisor owns (mirrors DailyTripLogViewSet's `mine` filter).
            from app.models.schedule_masters.trip_plan import TripPlan
            from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment

            supervised_plan_ids = TripPlan.objects.filter(
                supervisor_id=self.request.user.staff_unique_id,
            ).values("unique_id")
            supervised_assignment_ids = DailyTripAssignment.objects.filter(
                trip_plan_id__in=supervised_plan_ids,
            ).values("unique_id")
            queryset = queryset.filter(
                trip_assignment_id__in=supervised_assignment_ids
            )

        if trip_assignment:
            queryset = queryset.filter(trip_assignment_id=trip_assignment)
        if trip_collection_point:
            queryset = queryset.filter(trip_collection_point_id=trip_collection_point)
        if bin_id:
            queryset = queryset.filter(bin_id=bin_id)
        if panchayat:
            queryset = queryset.filter(panchayat_id=panchayat)
        if ward:
            queryset = queryset.filter(ward_id=ward)
        if zone:
            queryset = queryset.filter(zone_id=zone)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if collection_date:
            queryset = queryset.filter(collection_date=collection_date)
        if date_from:
            queryset = queryset.filter(collection_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(collection_date__lte=date_to)

        return queryset

    # -------------------------------------------------
    # DAILY TRIP COLLECTION POINT SYNC
    # -------------------------------------------------

    def _upsert_trip_log_for_assignment(self, assignment):
        """
        Keep admin BinCollectionEvent flow aligned with operator-mobile scans.

        DailyTripLog is created as soon as DailyTripCollectionPoint data exists
        for the trip, then submitted after every collection point is collected.
        """
        if not assignment:
            return

        children = assignment.trip_collection_points.filter(is_deleted=False)
        if not children.exists():
            return

        total_weight = children.aggregate(total=Sum("collected_weight_kg"))["total"] or 0
        vehicle_capacity = getattr(getattr(assignment, "vehicle_id", None), "capacity", None)
        trip_capacity = getattr(getattr(assignment, "trip_plan_id", None), "max_vehicle_capacity_kg", None)
        capacity = vehicle_capacity or trip_capacity
        exceeds_capacity = (
            bool(capacity)
            and total_weight
            and Decimal(str(total_weight)) > Decimal(str(capacity))
        )
        stored_weight = None if exceeds_capacity else total_weight
        remarks = (
            "Auto-generated from daily trip collection points; total weight exceeds capacity."
            if exceeds_capacity
            else "Auto-generated from daily trip collection points."
        )

        log, created = DailyTripLog.objects.get_or_create(
            trip_assignment_id=assignment,
            defaults={
                "collected_weight_kg": stored_weight,
                "remarks": remarks,
            },
        )
        if created:
            return

        # Always resync the real collected weight, even once the log has
        # been Verified — verification approves the trip, it doesn't freeze
        # the weight against collection points recorded/updated afterwards.
        log.collected_weight_kg = stored_weight
        if log.log_status != DailyTripLog.LOG_STATUS_VERIFIED:
            log.remarks = log.remarks or remarks
        log.save()

    def _sync_trip_cp_from_event(self, event):
        """
        Sync the linked DailyTripCollectionPoint whenever a BinCollectionEvent is saved.

        Always overwrites weight and marks Collected so the DTCP reflects the latest BCE data.
        Falls back to get_or_create by (assignment, collection_point) if the direct FK isn't
        resolved (defensive — trip_collection_point_id is NOT NULL in the model).
        """
        trip_cp = getattr(event, "trip_collection_point", None)

        if not trip_cp:
            assignment = getattr(event, "trip_assignment_id", None)
            collection_point = getattr(event, "collection_point_id", None)
            if not assignment or not collection_point:
                return
            trip_cp, _ = DailyTripCollectionPoint.objects.get_or_create(
                trip_assignment_id=assignment,
                collection_point_id=collection_point,
                defaults={
                    "bin_id": getattr(event, "bin_id", None),
                    "company_id": getattr(event, "company_id", None),
                    "project_id": getattr(event, "project_id", None),
                },
            )

        if not trip_cp:
            return

        event_status = getattr(event, "status", BinCollectionEvent.STATUS_COLLECTED)
        if event_status == BinCollectionEvent.STATUS_COLLECTED:
            trip_cp.collected_weight_kg = event.collected_weight_kg or 0
            trip_cp.collected_at = getattr(event, "created_at", None) or timezone.now()
            trip_cp.is_collected = True
            trip_cp.status = DailyTripCollectionPoint.STATUS_COLLECTED
            trip_cp.status_reason = None
            trip_cp.save(update_fields=[
                "collected_weight_kg",
                "collected_at",
                "is_collected",
                "status",
                "status_reason",
                "updated_at",
            ])
        else:
            # Not Collected / Collect Later — mirror onto the stop status
            # vocabulary (Missed / Skipped) without recording a weight.
            mapped_status = (
                DailyTripCollectionPoint.STATUS_MISSED
                if event_status == BinCollectionEvent.STATUS_NOT_COLLECTED
                else DailyTripCollectionPoint.STATUS_SKIPPED
            )
            # mark_status() already calls mark_completed_if_all_cps_collected()
            trip_cp.mark_status(mapped_status, getattr(event, "status_reason", None))

        assignment = trip_cp.trip_assignment
        if not assignment:
            return
        assignment.mark_completed_if_all_cps_collected()
        self._upsert_trip_log_for_assignment(assignment)

    # -------------------------------------------------
    # CREATE / UPDATE / DELETE
    # -------------------------------------------------

    @transaction.atomic
    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._sync_trip_cp_from_event(serializer.instance)

    @transaction.atomic
    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._sync_trip_cp_from_event(serializer.instance)

    @transaction.atomic
    def perform_destroy(self, instance):
        previous_data = self._serialize_instance(instance)
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active", "updated_at"])
        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )
