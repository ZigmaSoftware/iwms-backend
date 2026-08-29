from decimal import Decimal
import hashlib

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q, Sum
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.schedule_masters.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.services.openroute_service import OpenRouteServiceError, optimize_stops, route_stops
from app.serializers.core_modules.daily_operations.daily_trip_collection_point_serializer import (
    DailyTripCollectionPointSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class DailyTripCollectionPointViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    serializer_class = DailyTripCollectionPointSerializer
    lookup_field = "unique_id"
    permission_resource = "DailyTripCollectionPoint"

    filter_backends = [filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    ordering_fields = ["sequence", "status", "collected_at"]

    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "daily-trip-collection-point"

    def _ensure_assignment_stops(self, assignment_id):
        assignment = (
            DailyTripAssignment.objects.select_related("trip_plan_id")
            .filter(unique_id=assignment_id, is_deleted=False)
            .first()
        )
        if not assignment or not assignment.trip_plan_id_id:
            return assignment

        existing_cp_ids = set(
            DailyTripCollectionPoint.objects.filter(
                trip_assignment_id=assignment,
                is_deleted=False,
            ).values_list("collection_point_id_id", flat=True)
        )
        plan_stops = TripPlanCollectionPoint.objects.filter(
            trip_plan_id=assignment.trip_plan_id,
            is_active=True,
            is_deleted=False,
        ).select_related("collection_point_id", "bin_id").order_by("sequence")
        for stop in plan_stops:
            if not stop.collection_point_id_id or not stop.bin_id_id:
                # DailyTripCollectionPoint only models bin-collection stops;
                # household/bulk stops have no collection_point/bin to copy.
                continue
            if stop.collection_point_id_id in existing_cp_ids:
                continue
            DailyTripCollectionPoint.objects.create(
                trip_assignment_id=assignment,
                collection_point_id=stop.collection_point_id,
                bin_id=stop.bin_id,
                sequence=stop.sequence,
                is_collected=False,
                status=DailyTripCollectionPoint.STATUS_PENDING,
                created_by=getattr(assignment, "created_by", None),
            )
        return assignment

    def _ensure_current_stop(self, assignment):
        if not assignment or assignment.status != DailyTripAssignment.STATUS_IN_PROGRESS:
            return
        stops = DailyTripCollectionPoint.objects.filter(
            trip_assignment_id=assignment,
            is_deleted=False,
        )
        if stops.filter(status=DailyTripCollectionPoint.STATUS_IN_PROGRESS).exists():
            return
        next_stop = stops.filter(
            status=DailyTripCollectionPoint.STATUS_PENDING
        ).order_by("sequence").first()
        if next_stop:
            next_stop.status = DailyTripCollectionPoint.STATUS_IN_PROGRESS
            next_stop.save(update_fields=["status", "updated_at"])

    # DailyTripHouseholdCollection has no "In Progress" state and uses its
    # own vocabulary (Collect Later, Not Available, Not Collected) — map it
    # onto DailyTripCollectionPoint's status vocabulary so household rows
    # can sit in the same summary counts / tab filters / marker colors.
    _HOUSEHOLD_STATUS_MAP = {
        "Pending": DailyTripCollectionPoint.STATUS_PENDING,
        "Collect Later": DailyTripCollectionPoint.STATUS_PENDING,
        "Collected": DailyTripCollectionPoint.STATUS_COLLECTED,
        "Not Available": DailyTripCollectionPoint.STATUS_MISSED,
        "Not Collected": DailyTripCollectionPoint.STATUS_MISSED,
        "Skipped": DailyTripCollectionPoint.STATUS_SKIPPED,
    }

    def _household_rows_for_assignment(self, assignment):
        """DailyTripCollectionPointSerializer-shaped dicts for one
        assignment's household stops (DailyTripHouseholdCollection), which
        `get_queryset()` never sees since it only reads
        DailyTripCollectionPoint (bin-collection stops). Lets the tracking
        endpoint show real rows/pins/counts for household-only trips."""
        stops = list(
            DailyTripHouseholdCollection.objects.select_related(
                "customer_id", "trip_assignment_id", "trip_assignment_id__trip_plan_id",
            )
            .filter(trip_assignment_id=assignment, is_deleted=False)
            .order_by("sequence")
        )
        rows = []
        for stop in stops:
            customer = stop.customer_id
            if not customer:
                continue
            mapped_status = self._HOUSEHOLD_STATUS_MAP.get(
                stop.status, DailyTripCollectionPoint.STATUS_PENDING
            )
            rows.append({
                "unique_id": stop.unique_id,
                "trip_assignment_id": assignment.unique_id,
                "trip_assignment": {
                    "unique_id": assignment.unique_id,
                    "trip_date": assignment.trip_date,
                    "scheduled_time": assignment.scheduled_time,
                    "status": assignment.status,
                    "approval_status": assignment.approval_status,
                    "trip_plan_id": getattr(assignment.trip_plan_id, "unique_id", None),
                    "trip_plan_display_code": getattr(assignment.trip_plan_id, "display_code", None),
                },
                "collection_point_id": None,
                "collection_point": {
                    "unique_id": customer.unique_id,
                    "cp_name": customer.customer_name,
                    "latitude": customer.latitude,
                    "longitude": customer.longitude,
                    "panchayat_id": getattr(stop.panchayat_id, "unique_id", None),
                    "panchayat_name": getattr(stop.panchayat_id, "panchayat_name", None),
                    "ward_id": getattr(stop.ward_id, "unique_id", None),
                    "ward_name": getattr(stop.ward_id, "ward_name", None),
                    "zone_id": getattr(stop.zone_id, "unique_id", None),
                    "zone_name": getattr(stop.zone_id, "zone_name", None),
                },
                "zone_id": getattr(stop.zone_id, "unique_id", None),
                "ward_id": getattr(stop.ward_id, "unique_id", None),
                "panchayat_id": getattr(stop.panchayat_id, "unique_id", None),
                "bin_id": None,
                "bin": None,
                "sequence": stop.sequence,
                "is_collected": stop.is_collected,
                "collected_at": stop.collected_at,
                "collected_weight_kg": stop.collected_weight_kg,
                "collected_by": None,
                "collected_by_staff": None,
                "status": mapped_status,
                "status_reason": stop.status_reason,
                "status_latitude": stop.status_latitude,
                "status_longitude": stop.status_longitude,
                "created_at": stop.created_at,
                "updated_at": stop.updated_at,
            })
        return rows

    def _latest_vehicle_start(self, assignment):
        latest_event = (
            BinCollectionEvent.objects.filter(trip_assignment_id=assignment)
            .exclude(driver_latitude=None)
            .exclude(driver_longitude=None)
            .order_by("-created_at")
            .first()
        )
        if not latest_event:
            return None
        return [
            float(latest_event.driver_longitude),
            float(latest_event.driver_latitude),
        ]

    def _optimize_assignment(self, assignment_id, vehicle_start=None):
        assignment = self._ensure_assignment_stops(assignment_id)
        if not assignment:
            raise OpenRouteServiceError("Daily Trip Assignment was not found.")

        stops = list(
            self.get_queryset()
            .filter(trip_assignment_id__unique_id=assignment_id)
            .order_by("sequence")
        )
        completed_stops = [
            stop for stop in stops
            if stop.status == DailyTripCollectionPoint.STATUS_COLLECTED
        ]
        remaining_stops = [
            stop for stop in stops
            if stop.status != DailyTripCollectionPoint.STATUS_COLLECTED
        ]
        routable = [
            {
                "id": stop.unique_id,
                "location": [
                    float(stop.collection_point_id.longitude),
                    float(stop.collection_point_id.latitude),
                ],
            }
            for stop in remaining_stops
        ]
        latest_vehicle_start = self._latest_vehicle_start(assignment)
        resolved_vehicle_start = vehicle_start or latest_vehicle_start
        optimized = optimize_stops(routable, resolved_vehicle_start)
        by_id = {stop.unique_id: stop for stop in stops}
        with transaction.atomic():
            for index, stop in enumerate(completed_stops, start=1):
                stop.sequence = index
            for index, stop_id in enumerate(
                optimized["ordered_ids"],
                start=len(completed_stops) + 1,
            ):
                stop = by_id[stop_id]
                stop.sequence = index
            DailyTripCollectionPoint.objects.bulk_update(stops, ["sequence"])
        optimized["all_ordered_ids"] = [
            *[stop.unique_id for stop in completed_stops],
            *optimized["ordered_ids"],
        ]
        optimized["optimized_stop_count"] = len(remaining_stops)
        optimized["completed_stop_count"] = len(completed_stops)
        optimized["vehicle_no"] = getattr(assignment.vehicle_id, "vehicle_no", None)
        optimized["vehicle_start_source"] = (
            "request"
            if vehicle_start
            else "latest_gps"
            if latest_vehicle_start
            else "first_collection_point"
        )
        return optimized

    def _optimize_assignment_silently(self, assignment_id):
        try:
            self._optimize_assignment(assignment_id)
        except OpenRouteServiceError:
            # CRUD remains available if ORS is unavailable; manual optimization reports errors.
            pass

    def _upsert_trip_log_for_assignment(self, assignment):
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
        # Always store the real weight so the log appears in waste comparison reports.
        # Over-capacity trips are flagged in remarks for operator review.
        remarks = (
            "Auto-generated from daily trip collection points; total weight exceeds capacity."
            if exceeds_capacity
            else "Auto-generated from daily trip collection points."
        )

        log, created = DailyTripLog.objects.get_or_create(
            trip_assignment_id=assignment,
            defaults={
                "collected_weight_kg": total_weight,
                "remarks": remarks,
            },
        )
        if created:
            return

        # Always resync the real collected weight, even once the log has
        # been Verified — verification approves the trip, it doesn't freeze
        # the weight against collection points recorded/updated afterwards.
        log.collected_weight_kg = total_weight
        if log.log_status != DailyTripLog.LOG_STATUS_VERIFIED:
            log.remarks = log.remarks or remarks
        log.save()

    def _sync_bin_collection_event(self, instance):
        """Keep a BinCollectionEvent in sync with this stop's recorded weight.

        Waste-type reports (waste_type_breakdown.py) attribute weight by
        waste type from BinCollectionEvent rows only. Weight recorded here
        (e.g. via admin/manual entry rather than the mobile bin-scan flow)
        would otherwise never appear under its real waste type and fall
        into the "Unclassified" bucket despite being live/correct at the
        DailyTripLog total level.
        """
        if not instance.is_collected or not instance.collected_weight_kg:
            return
        assignment = instance.trip_assignment_id
        waste_type = getattr(instance.bin_id, "wastetype_id", None)
        if not waste_type:
            return
        field_values = {
            "company_id": instance.company_id or assignment.company_id,
            "project_id": instance.project_id or assignment.project_id,
            "trip_assignment_id": assignment,
            "collection_point_id": instance.collection_point_id,
            "bin_id": instance.bin_id,
            "panchayat_id": instance.panchayat_id,
            "ward_id": instance.ward_id,
            "zone_id": instance.zone_id,
            "waste_type_id": waste_type,
            "vehicle_id": getattr(assignment, "vehicle_id", None),
            "collected_weight_kg": instance.collected_weight_kg,
            "collection_date": assignment.trip_date,
        }
        existing = BinCollectionEvent.objects.filter(
            trip_collection_point_id=instance, is_deleted=False,
        ).order_by("-created_at").first()
        if existing:
            for field, value in field_values.items():
                setattr(existing, field, value)
            existing.save()
        else:
            BinCollectionEvent.objects.create(
                trip_collection_point_id=instance, **field_values
            )

    def _sync_assignment_and_log(self, instance):
        if not instance:
            return
        assignment = instance.trip_assignment_id
        if instance.is_collected:
            assignment.mark_completed_if_all_cps_collected()
        self._sync_bin_collection_event(instance)
        self._upsert_trip_log_for_assignment(assignment)

    def get_queryset(self):
        queryset = (
            DailyTripCollectionPoint.objects.select_related(
                "company_id",
                "project_id",
                "trip_assignment_id",
                "trip_assignment_id__trip_plan_id",
                "collection_point_id",
                "collection_point_id__panchayat_id",
                "zone_id",
                "ward_id",
                "ward_id__zone_id",
                "panchayat_id",
                "bin_id",
                "bin_id__wastetype_id",
                "collected_by",
            )
            .prefetch_related(
                "collection_point_id__wards",
                "collection_point_id__wards__zone_id",
            )
            .filter(is_deleted=False)
        )

        params = self.request.query_params
        assignment = params.get("trip_assignment_id")
        company = params.get("company_id")
        project = params.get("project_id")
        collection_point = params.get("collection_point_id")
        bin_id = params.get("bin_id")
        status_value = params.get("status")
        is_collected = params.get("is_collected")
        trip_date = params.get("date") or params.get("trip_date")
        staff_template = params.get("staff_template_id")
        alt_staff_template = params.get("alt_staff_template_id")
        zone = params.get("zone_id")
        ward = params.get("ward_id")
        panchayat = params.get("panchayat_id")
        search = params.get("search")

        if company:
            queryset = queryset.filter(company_id__unique_id=company)
        if project:
            queryset = queryset.filter(project_id__unique_id=project)
        if assignment:
            queryset = queryset.filter(trip_assignment_id__unique_id=assignment)
        if collection_point:
            queryset = queryset.filter(collection_point_id__unique_id=collection_point)
        if bin_id:
            queryset = queryset.filter(bin_id__unique_id=bin_id)
        if status_value and getattr(self, "action", None) != "tracking":
            queryset = queryset.filter(status=status_value)
        if is_collected is not None:
            queryset = queryset.filter(
                is_collected=str(is_collected).lower() in {"1", "true", "yes"}
            )
        if trip_date and not assignment:
            queryset = queryset.filter(trip_assignment_id__trip_date=trip_date)
        if staff_template:
            queryset = queryset.filter(
                trip_assignment_id__staff_template_id__unique_id=staff_template
            )
        if alt_staff_template:
            queryset = queryset.filter(
                trip_assignment_id__alt_staff_template_id__unique_id=alt_staff_template
            )
        if zone:
            queryset = queryset.filter(zone_id__unique_id=zone)
        if ward:
            queryset = queryset.filter(ward_id__unique_id=ward)
        if panchayat:
            queryset = queryset.filter(panchayat_id__unique_id=panchayat)
        if search:
            queryset = queryset.filter(
                Q(collection_point_id__cp_name__icontains=search)
                | Q(trip_assignment_id__unique_id__icontains=search)
                | Q(bin_id__bin_name__icontains=search)
            )

        return queryset

    @action(detail=False, methods=["get"], url_path="tracking")
    def tracking(self, request):
        assignment_id = request.query_params.get("trip_assignment_id")
        selected_assignment = None
        if assignment_id:
            selected_assignment = self._ensure_assignment_stops(assignment_id)
            self._ensure_current_stop(selected_assignment)

        route_queryset = self.filter_queryset(self.get_queryset()).order_by(
            "trip_assignment_id", "sequence"
        )
        status_value = request.query_params.get("status")

        # DailyTripCollectionPoint only models bin-collection stops; a
        # household-only trip (see DailyTripHouseholdCollection) has none,
        # so route_queryset alone would be empty for it. Only safe to merge
        # in household rows when one specific trip was requested — that's
        # the only case where the assignment is resolved up front.
        household_rows = (
            self._household_rows_for_assignment(selected_assignment)
            if selected_assignment
            else []
        )

        bin_route_rows = list(
            self.get_serializer(route_queryset[:500], many=True).data
        )
        route_rows = sorted(
            bin_route_rows + household_rows, key=lambda row: row["sequence"]
        )

        def matches_status(row):
            if not status_value:
                return True
            if status_value == DailyTripCollectionPoint.STATUS_MISSED:
                return row["status"] in {
                    DailyTripCollectionPoint.STATUS_MISSED,
                    DailyTripCollectionPoint.STATUS_SKIPPED,
                }
            return row["status"] == status_value

        filtered_rows = [row for row in route_rows if matches_status(row)]
        page = max(int(request.query_params.get("page", 1)), 1)
        page_size = min(max(int(request.query_params.get("page_size", 20)), 1), 100)
        total = len(filtered_rows)
        start = (page - 1) * page_size
        page_rows = filtered_rows[start:start + page_size]

        route_total = len(route_rows)
        completed = sum(row["status"] == DailyTripCollectionPoint.STATUS_COLLECTED for row in route_rows)
        in_progress = sum(row["status"] == DailyTripCollectionPoint.STATUS_IN_PROGRESS for row in route_rows)
        pending = sum(row["status"] == DailyTripCollectionPoint.STATUS_PENDING for row in route_rows)
        missed = sum(
            row["status"] in {DailyTripCollectionPoint.STATUS_SKIPPED, DailyTripCollectionPoint.STATUS_MISSED}
            for row in route_rows
        )

        assignment = selected_assignment
        if not assignment:
            first_bin_row = route_queryset.first()
            assignment = first_bin_row.trip_assignment_id if first_bin_row else None
        if assignment_id and not assignment:
            assignment = (
                DailyTripAssignment.objects.filter(
                    unique_id=assignment_id,
                    is_deleted=False,
                )
                .select_related("vehicle_id")
                .first()
            )
        latest_event = None
        if assignment:
            latest_event = (
                BinCollectionEvent.objects.filter(trip_assignment_id=assignment)
                .exclude(driver_latitude=None)
                .exclude(driver_longitude=None)
                .select_related("collection_point_id")
                .order_by("-created_at")
                .first()
            )
        next_stop = next(
            (
                row for row in route_rows
                if row["status"] in {
                    DailyTripCollectionPoint.STATUS_PENDING,
                    DailyTripCollectionPoint.STATUS_IN_PROGRESS,
                }
                and row.get("collection_point")
            ),
            None,
        )

        return Response({
            "count": total,
            "page": page,
            "page_size": page_size,
            "summary": {
                "total": route_total,
                "completed": completed,
                "in_progress": in_progress,
                "pending": pending,
                "missed": missed,
                "completion_percentage": round((completed / route_total) * 100, 2) if route_total else 0,
            },
            "results": page_rows,
            "route_results": route_rows,
            "vehicle_tracking": {
                "vehicle_no": getattr(getattr(assignment, "vehicle_id", None), "vehicle_no", None),
                "current_location": None if not latest_event else {
                    "latitude": latest_event.driver_latitude,
                    "longitude": latest_event.driver_longitude,
                    "recorded_at": latest_event.created_at,
                    "collection_point": latest_event.collection_point_id.cp_name,
                },
                "next_collection_point": None if not next_stop else {
                    "unique_id": next_stop["collection_point"]["unique_id"],
                    "cp_name": next_stop["collection_point"]["cp_name"],
                    "latitude": next_stop["collection_point"]["latitude"],
                    "longitude": next_stop["collection_point"]["longitude"],
                },
                "remaining_collection_points": pending + in_progress,
            },
        })

    @action(detail=False, methods=["get"], url_path="tracking-overview")
    def tracking_overview(self, request):
        assignments = DailyTripAssignment.objects.select_related(
            "vehicle_id",
            "trip_plan_id",
        ).filter(is_deleted=False)
        company = request.query_params.get("company_id")
        project = request.query_params.get("project_id")
        trip_date = request.query_params.get("date") or request.query_params.get("trip_date")
        if company:
            assignments = assignments.filter(company_id__unique_id=company)
        if project:
            assignments = assignments.filter(project_id__unique_id=project)
        if trip_date:
            assignments = assignments.filter(trip_date=trip_date)
        assignments = assignments.order_by("-trip_date", "-scheduled_time")[:30]

        trips = []
        aggregate = {"total": 0, "completed": 0, "in_progress": 0, "pending": 0, "missed": 0}
        for assignment in assignments:
            self._ensure_assignment_stops(assignment.unique_id)
            self._ensure_current_stop(assignment)
            stops = list(
                DailyTripCollectionPoint.objects.select_related(
                    "collection_point_id",
                    "collection_point_id__panchayat_id",
                    "trip_assignment_id",
                    "trip_assignment_id__trip_plan_id",
                    "bin_id",
                    "bin_id__wastetype_id",
                    "collected_by",
                    "company_id",
                    "project_id",
                )
                .prefetch_related(
                    "collection_point_id__wards",
                    "collection_point_id__wards__zone_id",
                )
                .filter(trip_assignment_id=assignment, is_deleted=False)
                .order_by("sequence")
            )
            if not stops:
                continue

            completed = sum(stop.status == DailyTripCollectionPoint.STATUS_COLLECTED for stop in stops)
            in_progress = sum(stop.status == DailyTripCollectionPoint.STATUS_IN_PROGRESS for stop in stops)
            pending = sum(stop.status == DailyTripCollectionPoint.STATUS_PENDING for stop in stops)
            missed = sum(
                stop.status in [
                    DailyTripCollectionPoint.STATUS_MISSED,
                    DailyTripCollectionPoint.STATUS_SKIPPED,
                ]
                for stop in stops
            )
            aggregate["total"] += len(stops)
            aggregate["completed"] += completed
            aggregate["in_progress"] += in_progress
            aggregate["pending"] += pending
            aggregate["missed"] += missed

            plant = self._plant_for(assignment.project_id)
            route_input = [
                {
                    "id": stop.unique_id,
                    "location": [
                        float(stop.collection_point_id.longitude),
                        float(stop.collection_point_id.latitude),
                    ],
                }
                for stop in stops
            ]
            if plant:
                route_input.append({
                    "id": plant.unique_id,
                    "location": [float(plant.longitude), float(plant.latitude)],
                })
            # Live GPS wins when available; otherwise the vehicle is assumed
            # to still be at the plant — its real start/end point for
            # the day — falling back to route_stops' own first-stop default
            # only when the project has no plant set up.
            vehicle_start = self._latest_vehicle_start(assignment) or (
                [float(plant.longitude), float(plant.latitude)] if plant else None
            )
            route_signature = "|".join(
                [
                    assignment.unique_id,
                    str(vehicle_start),
                    *[
                        f"{stop.unique_id}:{stop.sequence}:{stop.collection_point_id.latitude}:{stop.collection_point_id.longitude}"
                        for stop in stops
                    ],
                    f"plant:{plant.unique_id}" if plant else "plant:none",
                ]
            )
            cache_key = f"daily-trip-overview-route:{hashlib.sha1(route_signature.encode()).hexdigest()}"
            route = cache.get(cache_key)
            if route is None:
                route = route_stops(route_input, vehicle_start)
                cache.set(cache_key, route, timeout=300)
            trips.append({
                "assignment_id": assignment.unique_id,
                "trip_date": assignment.trip_date,
                "status": assignment.status,
                "vehicle_no": getattr(assignment.vehicle_id, "vehicle_no", None),
                "summary": {
                    "total": len(stops),
                    "completed": completed,
                    "in_progress": in_progress,
                    "pending": pending,
                    "missed": missed,
                    "completion_percentage": round((completed / len(stops)) * 100, 2),
                },
                "distance_meters": route["distance"],
                "duration_seconds": route["duration"],
                "route_geojson": route["geometry"],
                "vehicle_start": route["vehicle_start"],
                "collection_points": self.get_serializer(stops, many=True).data,
            })

        aggregate["completion_percentage"] = (
            round((aggregate["completed"] / aggregate["total"]) * 100, 2)
            if aggregate["total"]
            else 0
        )
        return Response({"summary": aggregate, "trips": trips})

    def _plant_for(self, project):
        from app.models.masters.plant import Plant

        if not project:
            return None
        return Plant.objects.filter(project_id=project, is_active=True, is_deleted=False).first()

    def _route_stops_for_assignment(self, assignment):
        """RouteStop-shaped dicts for one assignment's real stops, with the
        project's plant (if any) appended as the final stop. Purely a
        read-time projection — never creates a DailyTripCollectionPoint row.

        A single physical collection point commonly has several bins (one
        per waste stream), each a separate DailyTripCollectionPoint row at
        the exact same coordinate — grouped here into one RouteStop per
        collection_point_id so the map shows one pin per real-world location
        instead of stacking N identical markers on top of each other. Order
        follows the group's earliest sequence; bin-level detail survives in
        `details["Bins"]`.
        """
        stops = list(
            DailyTripCollectionPoint.objects.select_related(
                "collection_point_id", "bin_id",
            )
            .filter(trip_assignment_id=assignment, is_deleted=False)
            .order_by("sequence")
        )

        grouped = {}
        for stop in stops:
            cp = stop.collection_point_id
            group = grouped.setdefault(cp.unique_id, {
                "id": stop.unique_id,
                "label": cp.cp_name,
                "type": "collection_point",
                "sequence": stop.sequence,
                "latitude": float(cp.latitude),
                "longitude": float(cp.longitude),
                "bins": [],
            })
            group["sequence"] = min(group["sequence"], stop.sequence)
            group["bins"].append(f"{stop.bin_id.bin_name} ({stop.status})")

        household_stops = list(
            DailyTripHouseholdCollection.objects.select_related("customer_id")
            .filter(trip_assignment_id=assignment, is_deleted=False)
            .order_by("sequence")
        )
        for stop in household_stops:
            customer = stop.customer_id
            if not customer or customer.latitude is None or customer.longitude is None:
                continue
            grouped[f"household:{stop.unique_id}"] = {
                "id": stop.unique_id,
                "label": customer.customer_name,
                "type": "household",
                "sequence": stop.sequence,
                "latitude": float(customer.latitude),
                "longitude": float(customer.longitude),
                "bins": [],
                "status": stop.status,
            }

        ordered_groups = sorted(grouped.values(), key=lambda group: group["sequence"])
        route_stops = [
            {
                "id": group["id"],
                "label": group["label"],
                "type": group["type"],
                "order": index + 1,
                "latitude": group["latitude"],
                "longitude": group["longitude"],
                "details": (
                    {"Bins": ", ".join(group["bins"])}
                    if group["type"] == "collection_point"
                    else {"Status": group.get("status", "")}
                ),
            }
            for index, group in enumerate(ordered_groups)
        ]

        plant = self._plant_for(assignment.project_id)
        if plant:
            plant_stop = {
                "id": plant.unique_id,
                "label": plant.name,
                "type": "plant",
                "latitude": float(plant.latitude),
                "longitude": float(plant.longitude),
                "details": {},
            }
            # The vehicle starts its day at the plant and returns there
            # at the end of the trip, so it's both the first and last stop.
            route_stops = [{**plant_stop, "order": 1}] + [
                {**stop, "order": stop["order"] + 1} for stop in route_stops
            ]
            route_stops.append({**plant_stop, "order": len(route_stops) + 1})

        return route_stops

    @action(detail=False, methods=["get"], url_path="static-route")
    def static_route(self, request):
        """Real, fixed-order stop list for one trip assignment — Start
        (implicit, the vehicle's own position) → collection points → dump
        yard — for the Static Route Map. Never reorders or optimizes."""
        assignment_id = request.query_params.get("trip_assignment_id")
        if not assignment_id:
            return Response(
                {"trip_assignment_id": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment = self._ensure_assignment_stops(assignment_id)
        if not assignment:
            return Response(
                {"detail": "Daily Trip Assignment was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        from app.models.schedule_masters.route_detour_waypoint import RouteDetourWaypoint

        waypoints = RouteDetourWaypoint.objects.filter(
            trip_assignment_id=assignment, is_active=True, is_deleted=False,
        ).order_by("after_stop_id", "sequence")

        return Response({
            "trip_assignment_id": assignment.unique_id,
            "trip_date": assignment.trip_date,
            "vehicle_no": getattr(assignment.vehicle_id, "vehicle_no", None),
            "stops": self._route_stops_for_assignment(assignment),
            "detour_waypoints": [
                {
                    "id": waypoint.unique_id,
                    "after_stop_id": waypoint.after_stop_id,
                    "sequence": waypoint.sequence,
                    "latitude": float(waypoint.latitude),
                    "longitude": float(waypoint.longitude),
                }
                for waypoint in waypoints
            ],
        })

    @action(detail=False, methods=["get"], url_path="static-routes")
    def static_routes(self, request):
        """Every trip assignment's fixed-order stop list at once, for the
        Static Route Map's "all routes" view. Supports the same
        company/project/date filters as tracking-overview."""
        assignments = DailyTripAssignment.objects.select_related(
            "vehicle_id", "project_id",
        ).filter(is_deleted=False)

        company = request.query_params.get("company_id")
        project = request.query_params.get("project_id")
        trip_date = request.query_params.get("date") or request.query_params.get("trip_date")
        if company:
            assignments = assignments.filter(company_id__unique_id=company)
        if project:
            assignments = assignments.filter(project_id__unique_id=project)
        if trip_date:
            assignments = assignments.filter(trip_date=trip_date)
        assignments = assignments.order_by("-trip_date", "-scheduled_time")[:30]

        routes = []
        for assignment in assignments:
            self._ensure_assignment_stops(assignment.unique_id)
            stops = self._route_stops_for_assignment(assignment)
            if not stops:
                continue
            routes.append({
                "trip_assignment_id": assignment.unique_id,
                "trip_date": assignment.trip_date,
                "vehicle_no": getattr(assignment.vehicle_id, "vehicle_no", None),
                "stops": stops,
            })

        return Response({"routes": routes})

    @action(detail=False, methods=["post"], url_path="route-static")
    def route_static(self, request):
        """Return road-following geometry for a caller-supplied, fixed stop order.

        Unlike optimize-route, this never reorders stops — it only asks
        OpenRouteService to draw the road path through the given sequence.
        """
        raw_stops = request.data.get("stops")
        if not isinstance(raw_stops, list) or len(raw_stops) < 2:
            return Response(
                {"stops": "Provide at least 2 stops as [{id, latitude, longitude}, ...]."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        route_input = []
        for stop in raw_stops:
            try:
                route_input.append({
                    "id": str(stop["id"]),
                    "location": [float(stop["longitude"]), float(stop["latitude"])],
                })
            except (KeyError, TypeError, ValueError):
                return Response(
                    {"stops": "Each stop needs id, latitude and longitude."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            route = route_stops(route_input[1:], vehicle_start=route_input[0]["location"])
        except OpenRouteServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            "stop_order": [stop["id"] for stop in route_input],
            "distance_meters": route["distance"],
            "duration_seconds": route["duration"],
            "route_geojson": route["geometry"],
        })

    @action(detail=False, methods=["post"], url_path="optimize-route")
    def optimize_route(self, request):
        assignment_id = request.data.get("trip_assignment_id")
        if not assignment_id:
            return Response(
                {"trip_assignment_id": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            raw_vehicle_start = request.data.get("vehicle_start")
            vehicle_start = None
            if isinstance(raw_vehicle_start, (list, tuple)) and len(raw_vehicle_start) == 2:
                try:
                    vehicle_start = [float(raw_vehicle_start[0]), float(raw_vehicle_start[1])]
                except (TypeError, ValueError):
                    return Response(
                        {"vehicle_start": "Use [longitude, latitude]."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            optimized = self._optimize_assignment(assignment_id, vehicle_start)
        except OpenRouteServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            "trip_assignment_id": assignment_id,
            "optimized_order": optimized["all_ordered_ids"],
            "remaining_optimized_order": optimized["ordered_ids"],
            "optimized_stop_count": optimized["optimized_stop_count"],
            "completed_stop_count": optimized["completed_stop_count"],
            "vehicle_no": optimized["vehicle_no"],
            "vehicle_start": optimized["vehicle_start"],
            "vehicle_start_source": optimized["vehicle_start_source"],
            "distance_meters": optimized["distance"],
            "duration_seconds": optimized["duration"],
            "route_geojson": optimized["geometry"],
            "route_legs": optimized["route_legs"],
        })

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_collected:
            return Response(
                {"detail": "Collected trip collection points are read-only."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._sync_assignment_and_log(serializer.instance)
        self._optimize_assignment_silently(serializer.instance.trip_assignment_id_id)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._sync_assignment_and_log(serializer.instance)
        self._optimize_assignment_silently(serializer.instance.trip_assignment_id_id)

    def perform_destroy(self, instance):
        assignment_id = instance.trip_assignment_id_id
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
        self._optimize_assignment_silently(assignment_id)
