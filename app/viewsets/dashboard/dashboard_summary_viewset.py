"""Company/project-scoped dashboard summary API.

Modeled on the government backend's geo-hierarchy-scoped sibling
(iwms-government-backend/app/viewsets/dashboard_summary_viewset.py) but scoped
by company_id/project_id (+ optional ward_id) instead of state/district/
area_type/local_body/ward, matching how the rest of this codebase's list
endpoints are already called from the frontend (company_id/project_id query
params — see CompanyScopedViewSet._company/_project).
"""
from decimal import Decimal, ROUND_HALF_UP

from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.assets.bins import Bins
from app.models.customers.customercreation import CustomerCreation
from app.models.customers.wastecollection import WasteCollection
from app.models.grivences.complaints import Complaint
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.vehicle_breakdown import VehicleBreakdown
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.attendance import Recognized
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails
from app.models.user_creations.waste_collection_bluetooth import WasteType


TWO = Decimal("0.01")


def _round(value):
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(TWO, rounding=ROUND_HALF_UP)


def _model_has_field(model, name):
    try:
        model._meta.get_field(name)
        return True
    except Exception:
        return False


def _active(qs):
    model = qs.model
    if _model_has_field(model, "is_deleted"):
        qs = qs.filter(is_deleted=False)
    if _model_has_field(model, "is_active"):
        qs = qs.filter(is_active=True)
    return qs


class DashboardSummaryViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    # ==========================================================
    # SCOPE RESOLUTION — mirrors CompanyScopedViewSet's
    # _is_platform_super_admin/_company/_project, adapted for a plain
    # ViewSet reading company_id/project_id straight off query params
    # (not the X-Project-Id header) per the frontend's
    # useCompanyProjectSelection contract.
    # ==========================================================

    def _is_platform_super_admin(self, request):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "is_superuser", False)
            and getattr(user, "company_id", None) is None
        )

    def _resolve_scope(self, request):
        params = request.query_params
        ward_id = (params.get("ward_id") or "").strip() or None
        panchayat_id = (params.get("panchayat_id") or "").strip() or None
        zone_id = (params.get("zone_id") or "").strip() or None
        date_str = (params.get("date") or "").strip() or None
        project_id_param = (params.get("project_id") or "").strip() or None

        if self._is_platform_super_admin(request):
            company_id_param = (params.get("company_id") or "").strip() or None
            company = (
                Company.objects.filter(unique_id=company_id_param).first()
                if company_id_param
                else None
            )
        else:
            # Company users are force-scoped to their own company — any
            # company_id param is ignored so a mismatched value can never
            # leak another tenant's data.
            company = getattr(request.user, "company_id", None)

        project = None
        if company and project_id_param:
            project = Project.objects.filter(
                unique_id=project_id_param, company_id=company
            ).first()

        return company, project, ward_id, panchayat_id, zone_id, date_str

    def _resolve_date(self, date_str):
        target_date = timezone.localdate()
        if date_str:
            try:
                parsed = parse_date(date_str)
                if parsed is not None:
                    target_date = parsed
            except (ValueError, TypeError):
                pass
        return target_date

    def _scoped(self, qs, ctx):
        """Applies company/project/ward/panchayat/zone scoping. Returns
        .none() when no company is resolved (superadmin with no company_id
        param) so every aggregation downstream naturally yields zeroed
        output instead of risking a cross-tenant aggregate.

        Panchayat and zone filters combine with OR (a row is only ever
        panchayat-scoped — bin-collection trips — or zone-scoped —
        household/ward trips — never both), mirroring the same OR semantics
        used by the Daily/Monthly Waste Comparison report filters."""
        company = ctx["company"]
        if company is None:
            return qs.none()

        model = qs.model
        if _model_has_field(model, "company_id"):
            qs = qs.filter(company_id=company)

        project = ctx["project"]
        if project is not None and _model_has_field(model, "project_id"):
            qs = qs.filter(project_id=project)

        ward_id = ctx["ward_id"]
        if ward_id:
            if model is Ward:
                qs = qs.filter(unique_id=ward_id)
            elif _model_has_field(model, "ward") or _model_has_field(model, "ward_id"):
                qs = qs.filter(ward_id=ward_id)
            elif _model_has_field(model, "wards"):
                qs = qs.filter(wards__unique_id=ward_id).distinct()

        panchayat_id = ctx.get("panchayat_id")
        zone_id = ctx.get("zone_id")
        if panchayat_id or zone_id:
            location_filter = Q()
            has_location_field = False
            if panchayat_id:
                if model is Panchayat:
                    location_filter |= Q(unique_id=panchayat_id)
                    has_location_field = True
                elif _model_has_field(model, "panchayat") or _model_has_field(model, "panchayat_id"):
                    location_filter |= Q(panchayat_id=panchayat_id)
                    has_location_field = True
            if zone_id:
                if model is Zone:
                    location_filter |= Q(unique_id=zone_id)
                    has_location_field = True
                elif _model_has_field(model, "zone") or _model_has_field(model, "zone_id"):
                    location_filter |= Q(zone_id=zone_id)
                    has_location_field = True
            if has_location_field:
                qs = qs.filter(location_filter)
        return qs

    def _no_location(self, ctx):
        return {**ctx, "ward_id": None, "panchayat_id": None, "zone_id": None}

    # ==========================================================
    # MAIN ENDPOINT
    # ==========================================================

    def list(self, request):
        company, project, ward_id, panchayat_id, zone_id, date_str = self._resolve_scope(request)
        target_date = self._resolve_date(date_str)
        ctx = {
            "company": company,
            "project": project,
            "ward_id": ward_id,
            "panchayat_id": panchayat_id,
            "zone_id": zone_id,
        }

        return Response(
            {
                "filters": self._filter_options(ctx),
                "summary": {
                    "households": self._household_summary(ctx, target_date),
                    "attendance": self._attendance_summary(ctx, target_date),
                    "waste": self._waste_summary(ctx, target_date),
                    "bins": self._bin_summary(ctx, target_date),
                    "operations": self._collection_type_summary(ctx, target_date),
                    "vehicles": self._vehicle_summary(ctx),
                    "grievances": self._grievance_summary(ctx),
                    "masters": self._master_summary(ctx),
                },
                "recent_grievances": self._recent_grievances(ctx),
                "critical_alerts": self._critical_alerts(ctx),
                "vehicle_performance": self._vehicle_performance(ctx, target_date),
                "trip_performance": self._trip_performance(ctx, target_date),
                "team_performance": self._team_performance(ctx, target_date),
                "ward_performance": self._ward_performance(ctx, target_date),
                "collection_progress": self._collection_progress(ctx, target_date),
                "vehicle_status_detail": self._vehicle_status_detail(ctx),
                "as_of": timezone.now().isoformat(),
            }
        )

    # ==========================================================
    # FILTERS
    # ==========================================================

    def _filter_options(self, ctx):
        panchayat_qs = self._scoped(
            Panchayat.objects.filter(is_deleted=False), self._no_location(ctx)
        ).order_by("panchayat_name")
        zone_qs = self._scoped(
            Zone.objects.filter(is_deleted=False), self._no_location(ctx)
        ).order_by("zone_name")
        # Wards cascade under whichever panchayat/zone is selected (a ward
        # belongs to exactly one of the two — see Ward.clean()'s XOR rule) —
        # scoped by the full ctx (ward/panchayat/zone) so picking a panchayat
        # or zone narrows the Wards dropdown to just that location's wards.
        ward_qs = self._scoped(
            Ward.objects.filter(is_deleted=False), {**ctx, "ward_id": None}
        ).order_by("ward_name")
        return {
            "wards": [{"id": w.unique_id, "name": w.ward_name} for w in ward_qs[:1000]],
            "panchayats": [
                {"id": p.unique_id, "name": p.panchayat_name} for p in panchayat_qs[:1000]
            ],
            "zones": [{"id": z.unique_id, "name": z.zone_name} for z in zone_qs[:1000]],
        }

    # ==========================================================
    # SUMMARY — HOUSEHOLDS
    # ==========================================================

    def _household_summary(self, ctx, target_date=None):
        customers = self._scoped(_active(CustomerCreation.objects.all()), ctx)
        stops_qs = self._scoped(
            DailyTripHouseholdCollection.objects.filter(
                is_deleted=False,
                collection_type=DailyTripHouseholdCollection.COLLECTION_TYPE_HOUSEHOLD,
                trip_assignment_id__trip_plan_id__collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
            ),
            ctx,
        )
        if target_date:
            stops_qs = stops_qs.filter(trip_assignment_id__trip_date=target_date)

        all_customer_ids = set(customers.values_list("unique_id", flat=True).distinct())

        collected_ids = (
            set(
                stops_qs.filter(status=DailyTripHouseholdCollection.STATUS_COLLECTED)
                .values_list("customer_id", flat=True)
                .distinct()
            )
            & all_customer_ids
        )
        not_available_ids = (
            set(
                stops_qs.filter(status=DailyTripHouseholdCollection.STATUS_MISSED)
                .values_list("customer_id", flat=True)
                .distinct()
            )
            & all_customer_ids
        ) - collected_ids
        not_collected_ids = (
            set(
                stops_qs.filter(
                    status__in=[
                        DailyTripHouseholdCollection.STATUS_PENDING,
                        DailyTripHouseholdCollection.STATUS_NOT_COLLECTED,
                        DailyTripHouseholdCollection.STATUS_COLLECT_LATER,
                        DailyTripHouseholdCollection.STATUS_SKIPPED,
                    ]
                )
                .values_list("customer_id", flat=True)
                .distinct()
            )
            & all_customer_ids
        ) - collected_ids - not_available_ids

        accounted_ids = collected_ids | not_available_ids | not_collected_ids
        not_collected_ids |= all_customer_ids - accounted_ids

        return {
            "total_customers": len(all_customer_ids),
            "collected": len(collected_ids),
            "not_available": len(not_available_ids),
            "not_collected": len(not_collected_ids),
        }

    # ==========================================================
    # SUMMARY — ATTENDANCE
    # ==========================================================

    def _attendance_summary(self, ctx, target_date=None):
        staff = self._scoped(
            StaffcreationOfficeDetails.objects.filter(is_deleted=False, active_status=True),
            ctx,
        )
        attendance_filter = Q(staff__in=staff, punch_type="IN")
        if target_date:
            attendance_filter &= Q(recognition_date=target_date)
        attendance = Recognized.objects.filter(attendance_filter)
        present = attendance.values("staff_id").distinct().count()
        total = staff.count()
        return {
            "total": total,
            "present": present,
            "absent": max(total - present, 0),
            "leave": 0,
        }

    # ==========================================================
    # SUMMARY — WASTE
    # ==========================================================

    def _waste_summary(self, ctx, target_date=None):
        household_qs = self._scoped(
            WasteCollection.objects.filter(is_deleted=False).filter(
                Q(trip_assignment_id__isnull=True)
                | Q(
                    trip_assignment_id__trip_plan_id__collection_type__in=[
                        TripPlan.COLLECTION_TYPE_HOUSEHOLD,
                        TripPlan.COLLECTION_TYPE_BULK,
                    ]
                )
            ),
            ctx,
        )
        bin_qs = self._scoped(
            BinCollectionEvent.objects.filter(
                is_deleted=False,
                status=BinCollectionEvent.STATUS_COLLECTED,
                trip_assignment_id__trip_plan_id__collection_type=TripPlan.COLLECTION_TYPE_BIN,
            ),
            ctx,
        )
        if target_date:
            household_qs = household_qs.filter(collection_date=target_date)
            bin_qs = bin_qs.filter(collection_date=target_date)

        totals = household_qs.aggregate(
            total_kg=Sum("total_quantity"),
            wet_kg=Sum("wet_waste"),
            dry_kg=Sum("dry_waste"),
            mixed_kg=Sum("mixed_waste"),
            sanitary_kg=Sum("sanitary_waste"),
        )
        bin_rows = bin_qs.values("waste_type_id", "waste_type_id__waste_type_name").annotate(
            total_kg=Sum("collected_weight_kg")
        )
        household_total = _round(totals["total_kg"])
        bin_total = sum((_round(row["total_kg"]) for row in bin_rows), Decimal("0"))
        total = household_total + bin_total

        master_rows = list(
            self._scoped(WasteType.objects.filter(is_deleted=False, is_active=True), self._no_location(ctx))
            .order_by("waste_type_name", "unique_id")
            .values("unique_id", "waste_type_name")
        )
        breakdown = {
            row["unique_id"]: {
                "waste_type_id": row["unique_id"],
                "waste_type_name": row["waste_type_name"],
                "weight_kg": Decimal("0"),
            }
            for row in master_rows
        }
        master_id_by_name = {
            row["waste_type_name"].strip().casefold(): row["unique_id"] for row in master_rows
        }
        others_kg = Decimal("0")

        def add_weight(weight, *, waste_type_id=None, waste_type_name=""):
            nonlocal others_kg
            amount = _round(weight)
            if amount <= 0:
                return
            master_id = waste_type_id if waste_type_id in breakdown else None
            if master_id is None and waste_type_name:
                master_id = master_id_by_name.get(waste_type_name.strip().casefold())
            if master_id is None:
                others_kg += amount
            else:
                breakdown[master_id]["weight_kg"] += amount

        for column, label in (
            ("wet_kg", "Wet Waste"),
            ("dry_kg", "Dry Waste"),
            ("mixed_kg", "Mixed Waste"),
            ("sanitary_kg", "Sanitary Waste"),
        ):
            add_weight(totals[column], waste_type_name=label)
        classified_household_kg = sum(
            (_round(totals[column]) for column in ("wet_kg", "dry_kg", "mixed_kg", "sanitary_kg")),
            Decimal("0"),
        )
        if household_total > classified_household_kg:
            others_kg += household_total - classified_household_kg
        for row in bin_rows:
            add_weight(
                row["total_kg"],
                waste_type_id=row["waste_type_id"],
                waste_type_name=row["waste_type_id__waste_type_name"] or "",
            )

        waste_type_breakdown = []
        for item in breakdown.values():
            weight_kg = item["weight_kg"]
            waste_type_breakdown.append(
                {
                    "waste_type_id": item["waste_type_id"],
                    "waste_type_name": item["waste_type_name"],
                    "weight_kg": float(weight_kg),
                    "tons": float(_round(weight_kg / Decimal("1000"))),
                    "percentage": round(float(weight_kg / total * 100), 1) if total else 0,
                }
            )
        if others_kg > 0:
            waste_type_breakdown.append(
                {
                    "waste_type_id": "others",
                    "waste_type_name": "Others",
                    "weight_kg": float(others_kg),
                    "tons": float(_round(others_kg / Decimal("1000"))),
                    "percentage": round(float(others_kg / total * 100), 1) if total else 0,
                }
            )

        wet = sum(
            (
                Decimal(str(item["weight_kg"]))
                for item in waste_type_breakdown
                if "wet" in item["waste_type_name"].casefold()
            ),
            Decimal("0"),
        )
        dry = sum(
            (
                Decimal(str(item["weight_kg"]))
                for item in waste_type_breakdown
                if "dry" in item["waste_type_name"].casefold()
            ),
            Decimal("0"),
        )
        other = max(total - wet - dry, Decimal("0"))
        return {
            "total_kg": float(total),
            "total_tons": float(_round(total / Decimal("1000"))),
            "household_kg": float(household_total),
            "bin_kg": float(bin_total),
            "wet_kg": float(wet),
            "dry_kg": float(dry),
            "other_kg": float(other),
            "wet_tons": float(_round(wet / Decimal("1000"))),
            "dry_tons": float(_round(dry / Decimal("1000"))),
            "other_tons": float(_round(other / Decimal("1000"))),
            "waste_type_breakdown": waste_type_breakdown,
            "collections": household_qs.count() + bin_qs.count(),
            "household_collections": household_qs.count(),
            "bin_collections": bin_qs.count(),
        }

    # ==========================================================
    # SUMMARY — BINS
    # ==========================================================

    def _bin_summary(self, ctx, target_date=None):
        bins = self._scoped(_active(Bins.objects.all()), ctx)
        events = self._scoped(
            BinCollectionEvent.objects.filter(
                is_deleted=False,
                trip_assignment_id__trip_plan_id__collection_type=TripPlan.COLLECTION_TYPE_BIN,
            ),
            ctx,
        )
        if target_date:
            events = events.filter(collection_date=target_date)
        collected_bins = (
            events.filter(status=BinCollectionEvent.STATUS_COLLECTED)
            .values("bin_id")
            .distinct()
            .count()
        )
        total = bins.count()
        return {
            "total": total,
            "collected": collected_bins,
            "not_collected": max(total - collected_bins, 0),
        }

    # ==========================================================
    # SUMMARY — OPERATIONS (household / bin / bulk)
    # ==========================================================

    def _collection_type_summary(self, ctx, target_date=None):
        assignments = self._scoped(DailyTripAssignment.objects.filter(is_deleted=False), ctx)
        logs = self._scoped(
            DailyTripLog.objects.filter(is_deleted=False),
            ctx,
        )
        household_rows = self._scoped(
            DailyTripHouseholdCollection.objects.filter(
                is_deleted=False,
                collection_type=DailyTripHouseholdCollection.COLLECTION_TYPE_HOUSEHOLD,
                trip_assignment_id__trip_plan_id__collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
            ),
            ctx,
        )
        bin_events = self._scoped(
            BinCollectionEvent.objects.filter(
                is_deleted=False,
                status=BinCollectionEvent.STATUS_COLLECTED,
                trip_assignment_id__trip_plan_id__collection_type=TripPlan.COLLECTION_TYPE_BIN,
            ),
            ctx,
        )
        if target_date:
            assignments = assignments.filter(trip_date=target_date)
            logs = logs.filter(trip_date=target_date)
            household_rows = household_rows.filter(trip_assignment_id__trip_date=target_date)
            bin_events = bin_events.filter(collection_date=target_date)

        trip_totals = {
            row["trip_plan_id__collection_type"]: row["count"]
            for row in assignments.values("trip_plan_id__collection_type").annotate(
                count=Count("unique_id", distinct=True)
            )
        }
        trip_completed = {
            row["trip_assignment_id__trip_plan_id__collection_type"]: row["count"]
            for row in logs.values("trip_assignment_id__trip_plan_id__collection_type").annotate(
                count=Count("unique_id", distinct=True)
            )
        }
        household_collected = household_rows.filter(
            status=DailyTripHouseholdCollection.STATUS_COLLECTED
        )
        household_ward_ids = set(
            household_collected.exclude(customer_id__ward__isnull=True).values_list(
                "customer_id__ward", flat=True
            )
        )
        bin_ward_ids = set(bin_events.exclude(ward_id__isnull=True).values_list("ward_id", flat=True))

        def trip_metrics(collection_type):
            return {
                "trips_completed": trip_completed.get(collection_type, 0),
                "trips_total": trip_totals.get(collection_type, 0),
            }

        household = {
            **trip_metrics(TripPlan.COLLECTION_TYPE_HOUSEHOLD),
            "collections": household_collected.count(),
            "weight_kg": float(
                household_collected.aggregate(total=Sum("collected_weight_kg"))["total"] or 0
            ),
            "wards_completed": len(household_ward_ids),
        }
        bins = {
            **trip_metrics(TripPlan.COLLECTION_TYPE_BIN),
            "collections": bin_events.values("bin_id").distinct().count(),
            "weight_kg": float(
                bin_events.aggregate(total=Sum("collected_weight_kg"))["total"] or 0
            ),
            "wards_completed": len(bin_ward_ids),
        }
        bulk = trip_metrics(TripPlan.COLLECTION_TYPE_BULK)
        return {
            "available": True,
            "household": household,
            "bin": bins,
            "bulk": bulk,
            "trips_completed": sum(trip_completed.values()),
            "trips_total": sum(trip_totals.values()),
            "wards_completed": len(household_ward_ids | bin_ward_ids),
        }

    # ==========================================================
    # SUMMARY — VEHICLES
    # ==========================================================

    def _vehicle_summary(self, ctx):
        vehicles = self._scoped(_active(VehicleCreation.objects.all()), self._no_location(ctx))
        total = vehicles.count()
        active = vehicles.filter(is_active=True).count()
        return {
            "total": total,
            "active": active,
            "inactive": max(total - active, 0),
        }

    # ==========================================================
    # SUMMARY — GRIEVANCES
    # ==========================================================

    def _grievance_summary(self, ctx):
        qs = self._scoped(Complaint.objects.filter(is_deleted=False), self._no_location(ctx))
        counts = qs.aggregate(
            total=Count("unique_id"),
            resolved=Count("unique_id", filter=Q(status=Complaint.StatusChoices.CLOSED)),
            in_progress=Count("unique_id", filter=Q(status=Complaint.StatusChoices.PROGRESSING)),
        )
        total = counts["total"] or 0
        resolved = counts["resolved"] or 0
        in_progress = counts["in_progress"] or 0
        # Complaint only has two statuses (PROGRESSING/CLOSED), unlike the
        # reference's richer status model — there's no distinct "open but
        # unassigned" bucket to split out, so `open` stays 0 and everything
        # unresolved counts as in_progress.
        return {
            "total": total,
            "open": 0,
            "in_progress": in_progress,
            "resolved": resolved,
        }

    # ==========================================================
    # SUMMARY — MASTERS
    # ==========================================================

    def _master_summary(self, ctx):
        return {
            "wards": self._scoped(Ward.objects.filter(is_deleted=False), self._no_location(ctx)).count(),
        }

    # ==========================================================
    # VEHICLE PERFORMANCE
    # ==========================================================

    def _vehicle_performance(self, ctx, target_date=None):
        vehicles = list(
            self._scoped(
                VehicleCreation.objects.select_related("vehicle_type").filter(is_deleted=False),
                self._no_location(ctx),
            )[:20]
        )
        v_ids = [v.unique_id for v in vehicles]

        trip_agg = DailyTripAssignment.objects.filter(vehicle_id__in=v_ids, is_deleted=False)
        if target_date:
            trip_agg = trip_agg.filter(trip_date=target_date)
        trip_map = {
            r["vehicle_id"]: r["trip_count"]
            for r in trip_agg.values("vehicle_id").annotate(trip_count=Count("unique_id"))
        }

        waste_agg = DailyTripHouseholdCollection.objects.filter(
            trip_assignment_id__vehicle_id__in=v_ids, is_collected=True
        )
        if target_date:
            waste_agg = waste_agg.filter(trip_assignment_id__trip_date=target_date)
        waste_map = {
            r["trip_assignment_id__vehicle_id"]: r
            for r in waste_agg.values("trip_assignment_id__vehicle_id").annotate(
                total_kg=Sum("collected_weight_kg"),
                stop_count=Count("unique_id"),
            )
        }

        return [
            {
                "registration_no": v.vehicle_no,
                "vehicle_type": (
                    v.vehicle_type.vehicleType
                    if getattr(v, "vehicle_type_id", None) and v.vehicle_type
                    else ""
                ),
                "ward_name": "",
                "trips": trip_map.get(v.unique_id, 0),
                "waste_tons": round(
                    float((waste_map.get(v.unique_id, {})).get("total_kg") or 0) / 1000, 2
                ),
                "capacity_pct": min(
                    round(
                        float((waste_map.get(v.unique_id, {})).get("total_kg") or 0)
                        / max(float(v.capacity or 1), 1)
                        * 100,
                    ),
                    100,
                ),
                "status": "Active" if v.is_active else "Inactive",
            }
            for v in vehicles
        ]

    # ==========================================================
    # TRIP PERFORMANCE
    # ==========================================================

    def _trip_performance(self, ctx, target_date=None):
        qs = DailyTripAssignment.objects.filter(is_deleted=False).select_related(
            "vehicle_id", "trip_plan_id"
        )
        qs = self._scoped(qs, ctx)
        if target_date:
            qs = qs.filter(trip_date=target_date)
        qs = qs.order_by("-created_at")[:10]

        assignment_ids = [a.unique_id for a in qs]
        stop_counts = dict(
            DailyTripHouseholdCollection.objects.filter(trip_assignment_id__in=assignment_ids)
            .values("trip_assignment_id")
            .annotate(cnt=Count("unique_id"))
            .values_list("trip_assignment_id", "cnt")
        )
        weight_agg = dict(
            DailyTripHouseholdCollection.objects.filter(
                trip_assignment_id__in=assignment_ids, is_collected=True
            )
            .values("trip_assignment_id")
            .annotate(total_kg=Sum("collected_weight_kg"))
            .values_list("trip_assignment_id", "total_kg")
        )

        return [
            {
                "trip_id": a.trip_plan_id.display_code if a.trip_plan_id else a.unique_id,
                "vehicle_no": a.vehicle_id.vehicle_no if a.vehicle_id else "",
                "ward_name": "",
                "start_time": (
                    a.actual_start_time.strftime("%I:%M %p")
                    if a.actual_start_time
                    else (a.scheduled_time.strftime("%I:%M %p") if a.scheduled_time else "")
                ),
                "stops": stop_counts.get(a.unique_id, 0),
                "weight_tons": round(float(weight_agg.get(a.unique_id) or 0) / 1000, 2),
                "status": a.status,
            }
            for a in qs
        ]

    # ==========================================================
    # TEAM PERFORMANCE
    # ==========================================================

    def _team_performance(self, ctx, target_date=None):
        qs = DailyTripAssignment.objects.filter(
            is_deleted=False, staff_template_id__isnull=False
        ).select_related("staff_template_id", "vehicle_id")
        qs = self._scoped(qs, ctx)
        if target_date:
            qs = qs.filter(trip_date=target_date)

        team_agg = qs.values("staff_template_id").annotate(trip_count=Count("unique_id"))

        templates = StaffTemplate.objects.filter(
            unique_id__in=[r["staff_template_id"] for r in team_agg]
        )
        template_map = {t.unique_id: t for t in templates}

        assignment_ids = list(qs.values_list("unique_id", flat=True))
        waste_agg = {}
        if assignment_ids:
            waste_rows = (
                DailyTripHouseholdCollection.objects.filter(
                    trip_assignment_id__in=assignment_ids, is_collected=True
                )
                .values("trip_assignment_id")
                .annotate(total_kg=Sum("collected_weight_kg"))
            )
            for r in waste_rows:
                waste_agg[r["trip_assignment_id"]] = float(r["total_kg"] or 0)

        result = []
        for row in team_agg:
            tmpl = template_map.get(row["staff_template_id"])
            if not tmpl:
                continue
            staff_count = 2
            if tmpl.extra_operator_id:
                try:
                    staff_count += len(tmpl.extra_operator_id)
                except Exception:
                    pass
            result.append(
                {
                    "team_name": tmpl.display_code,
                    "ward_name": "",
                    "attendance_present": row["trip_count"],
                    "attendance_total": staff_count,
                    "trips": row["trip_count"],
                    "waste_tons": round(
                        sum(
                            waste_agg.get(aid, 0)
                            for aid in qs.filter(
                                staff_template_id=row["staff_template_id"]
                            ).values_list("unique_id", flat=True)
                        )
                        / 1000,
                        2,
                    ),
                    "score": min(round((row["trip_count"] / max(staff_count, 1)) * 20), 100),
                }
            )
        return sorted(result, key=lambda x: x["score"], reverse=True)[:10]

    # ==========================================================
    # WARD PERFORMANCE
    # ==========================================================

    def _ward_performance(self, ctx, target_date=None):
        ward_list = list(
            self._scoped(Ward.objects.filter(is_deleted=False), ctx).select_related("district_id")[:50]
        )
        ward_ids = [w.unique_id for w in ward_list]

        collection_qs = DailyTripHouseholdCollection.objects.filter(
            customer_id__ward__in=ward_ids,
            is_deleted=False,
            collection_type=DailyTripHouseholdCollection.COLLECTION_TYPE_HOUSEHOLD,
            trip_assignment_id__trip_plan_id__collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
        )
        if target_date:
            collection_qs = collection_qs.filter(trip_assignment_id__trip_date=target_date)

        agg = collection_qs.values("customer_id__ward").annotate(
            collected=Count("customer_id", filter=Q(is_collected=True), distinct=True),
            missed=Count("unique_id", filter=Q(status=DailyTripHouseholdCollection.STATUS_MISSED)),
            not_collected=Count(
                "unique_id",
                filter=Q(
                    status__in=[
                        DailyTripHouseholdCollection.STATUS_NOT_COLLECTED,
                        DailyTripHouseholdCollection.STATUS_SKIPPED,
                    ]
                ),
            ),
            household_kg=Sum("collected_weight_kg"),
        )
        ward_data = {r["customer_id__ward"]: r for r in agg}

        customer_agg = (
            self._scoped(_active(CustomerCreation.objects.filter(ward__in=ward_ids)), self._no_location(ctx))
            .values("ward")
            .annotate(total_customers=Count("unique_id"))
        )
        customer_data = {r["ward"]: r for r in customer_agg}

        bin_master_agg = (
            self._scoped(_active(Bins.objects.filter(ward_id__in=ward_ids)), self._no_location(ctx))
            .values("ward_id")
            .annotate(total_bins=Count("unique_id"))
        )
        bin_master_data = {r["ward_id"]: r for r in bin_master_agg}

        bin_qs = BinCollectionEvent.objects.filter(
            ward_id__in=ward_ids,
            is_deleted=False,
            trip_assignment_id__trip_plan_id__collection_type=TripPlan.COLLECTION_TYPE_BIN,
        )
        if target_date:
            bin_qs = bin_qs.filter(collection_date=target_date)
        bin_agg = bin_qs.values("ward_id").annotate(
            bin_kg=Sum("collected_weight_kg"),
            bin_collected=Count("bin_id", filter=Q(status=BinCollectionEvent.STATUS_COLLECTED), distinct=True),
        )
        bin_data = {r["ward_id"]: r for r in bin_agg}

        plan_agg = (
            TripPlan.objects.filter(wards__in=ward_ids, is_deleted=False)
            .values("wards__unique_id", "collection_type")
            .annotate(target_kg=Sum("max_vehicle_capacity_kg"))
        )
        household_target = {}
        bin_target = {}
        for r in plan_agg:
            wid = r["wards__unique_id"]
            if r["collection_type"] == TripPlan.COLLECTION_TYPE_HOUSEHOLD:
                household_target[wid] = float(r["target_kg"] or 0)
            elif r["collection_type"] == TripPlan.COLLECTION_TYPE_BIN:
                bin_target[wid] = float(r["target_kg"] or 0)

        assignment_rows = (
            DailyTripAssignment.objects.filter(wards__in=ward_ids, is_deleted=False)
            .order_by("-trip_date", "-scheduled_time")
            .values(
                "unique_id",
                "wards__unique_id",
                "trip_plan_id__collection_type",
                "trip_date",
                "actual_start_time",
                "scheduled_time",
                "vehicle_id__vehicle_no",
                "staff_template_id__driver_id__employee_name",
                "staff_template_id__operator_id__employee_name",
            )
        )

        trips_by_ward = {}
        seen_ward_types = set()
        for r in assignment_rows:
            wid = r["wards__unique_id"]
            collection_type = r["trip_plan_id__collection_type"]
            if not wid:
                continue
            key = (wid, collection_type)
            if key in seen_ward_types:
                continue
            seen_ward_types.add(key)
            trip_time = r["actual_start_time"] or r["scheduled_time"]
            trips_by_ward.setdefault(wid, []).append(
                {
                    "trip_id": r["unique_id"],
                    "collection_type": collection_type,
                    "driver_name": r["staff_template_id__driver_id__employee_name"] or "-",
                    "operator_name": r["staff_template_id__operator_id__employee_name"] or "-",
                    "vehicle_no": r["vehicle_id__vehicle_no"] or "-",
                    "trip_date": r["trip_date"].isoformat() if r["trip_date"] else None,
                    "trip_time": trip_time.strftime("%H:%M") if trip_time else None,
                }
            )

        result = []
        for w in ward_list:
            row = ward_data.get(w.unique_id, {})
            customer_row = customer_data.get(w.unique_id, {})
            bin_master_row = bin_master_data.get(w.unique_id, {})
            brow = bin_data.get(w.unique_id, {})
            household_kg = round(float(row.get("household_kg") or 0), 2)
            bin_kg = round(float(brow.get("bin_kg") or 0), 2)
            household_target_kg = round(household_target.get(w.unique_id, 0), 2)
            bin_target_kg = round(bin_target.get(w.unique_id, 0), 2)
            household_total = customer_row.get("total_customers", 0)
            bin_total = bin_master_row.get("total_bins", 0)
            result.append(
                {
                    "ward_id": w.unique_id,
                    "ward_name": w.ward_name,
                    "district_name": w.district_id.name if w.district_id_id else "",
                    "trips": trips_by_ward.get(w.unique_id, []),
                    "household_current_kg": household_kg,
                    "household_target_kg": household_target_kg,
                    "bin_current_kg": bin_kg,
                    "bin_target_kg": bin_target_kg,
                    "current_weight_kg": round(household_kg + bin_kg, 2),
                    "overall_weight_kg": round(household_target_kg + bin_target_kg, 2),
                    "waste_tons": round((household_kg + bin_kg) / 1000, 2),
                    "status": (
                        "delayed"
                        if row.get("not_collected", 0) > row.get("collected", 0)
                        else "no_vehicle"
                        if household_total == 0 and bin_total == 0
                        else "normal"
                    ),
                    "households_collected": row.get("collected", 0),
                    "households_total": household_total,
                    "bins_collected": brow.get("bin_collected", 0),
                    "bins_total": bin_total,
                    "completion_pct": round((row.get("collected", 0) / max(household_total, 1)) * 100, 1),
                }
            )
        return result

    # ==========================================================
    # COLLECTION PROGRESS (31-day time series)
    # ==========================================================

    def _collection_progress(self, ctx, target_date=None):
        household_qs = self._scoped(
            WasteCollection.objects.filter(is_deleted=False).filter(
                Q(trip_assignment_id__isnull=True)
                | Q(
                    trip_assignment_id__trip_plan_id__collection_type__in=[
                        TripPlan.COLLECTION_TYPE_HOUSEHOLD,
                        TripPlan.COLLECTION_TYPE_BULK,
                    ]
                )
            ),
            ctx,
        )
        bin_qs = self._scoped(
            BinCollectionEvent.objects.filter(
                is_deleted=False,
                status=BinCollectionEvent.STATUS_COLLECTED,
                trip_assignment_id__trip_plan_id__collection_type=TripPlan.COLLECTION_TYPE_BIN,
            ),
            ctx,
        )

        today = target_date or timezone.localdate()
        labels = [str(today - timedelta(days=30 - i)) for i in range(31)]

        daily = {
            d: {
                "count": 0,
                "total_kg": 0,
                "household_count": 0,
                "household_kg": 0,
                "bin_count": 0,
                "bin_kg": 0,
            }
            for d in labels
        }

        household_agg = (
            household_qs.filter(collection_date__gte=today - timedelta(days=30))
            .values("collection_date")
            .annotate(cnt=Count("unique_id"), total_kg=Sum("total_quantity"))
        )
        for r in household_agg:
            key = str(r["collection_date"])
            if key in daily:
                daily[key]["household_count"] = r["cnt"] or 0
                daily[key]["household_kg"] = float(r["total_kg"] or 0)

        bin_agg = (
            bin_qs.filter(collection_date__gte=today - timedelta(days=30))
            .values("collection_date")
            .annotate(cnt=Count("unique_id"), total_kg=Sum("collected_weight_kg"))
        )
        for r in bin_agg:
            key = str(r["collection_date"])
            if key in daily:
                daily[key]["bin_count"] = r["cnt"] or 0
                daily[key]["bin_kg"] = float(r["total_kg"] or 0)

        for values in daily.values():
            values["count"] = values["household_count"] + values["bin_count"]
            values["total_kg"] = values["household_kg"] + values["bin_kg"]

        max_val = max((v["count"] for v in daily.values()), default=1)
        return [
            {
                "label": d.split("-")[2],
                "value": daily[d]["count"],
                "pct": round((daily[d]["count"] / (max_val or 1)) * 100, 1),
                "total_kg": daily[d]["total_kg"],
                "household_count": daily[d]["household_count"],
                "household_kg": daily[d]["household_kg"],
                "bin_count": daily[d]["bin_count"],
                "bin_kg": daily[d]["bin_kg"],
            }
            for d in sorted(daily.keys())
        ]

    # ==========================================================
    # VEHICLE STATUS DETAIL
    # ==========================================================

    def _vehicle_status_detail(self, ctx):
        vehicles = self._scoped(VehicleCreation.objects.filter(is_deleted=False), self._no_location(ctx))
        total = vehicles.count()
        active = vehicles.filter(is_active=True).count()
        today = timezone.localdate()
        vehicles_with_trips_today = set(
            DailyTripAssignment.objects.filter(
                vehicle_id__in=vehicles.values("unique_id"), trip_date=today, is_deleted=False
            ).values_list("vehicle_id", flat=True)
        )
        idle_count = 0
        for v in vehicles.iterator():
            if not v.is_active:
                continue
            if v.unique_id not in vehicles_with_trips_today:
                idle_count += 1
        breakdowns = self._scoped(
            VehicleBreakdown.objects.filter(is_deleted=False, status=VehicleBreakdown.STATUS_REPORTED),
            self._no_location(ctx),
        )
        breakdown_count = breakdowns.count()
        return {
            "idle": idle_count,
            "breakdown": breakdown_count,
            "offline_gps": max(round(total * 0.06), 0),
        }

    # ==========================================================
    # CRITICAL ALERTS — merged open Complaint + non-rejected VehicleBreakdown
    # ==========================================================

    def _critical_alerts(self, ctx):
        complaints = list(
            self._scoped(
                Complaint.objects.filter(
                    is_deleted=False, status=Complaint.StatusChoices.PROGRESSING
                )
                .select_related("customer", "zone", "ward")
                .order_by("-created"),
                self._no_location(ctx),
            )[:10]
        )
        breakdowns = list(
            self._scoped(
                VehicleBreakdown.objects.filter(is_deleted=False)
                .exclude(status=VehicleBreakdown.STATUS_REJECTED)
                .select_related(
                    "breakdown_vehicle_id",
                    "replacement_vehicle_id",
                    "replacement_driver_id",
                    "replacement_operator_id",
                    "trip_assignment_id",
                    "trip_assignment_id__trip_plan_id",
                )
                .order_by("-created_at"),
                self._no_location(ctx),
            )[:10]
        )

        alerts = []
        for row in complaints:
            alerts.append(
                {
                    "id": row.unique_id,
                    "kind": "grievance",
                    "title": row.main_category or row.category,
                    "description": row.details or "",
                    "status": row.status,
                    "severity": "critical" if row.priority == Complaint.PriorityChoices.HIGH else "warning",
                    "created": row.created.isoformat() if row.created else None,
                    "updated": row.updated.isoformat() if row.updated else None,
                    "priority": row.priority,
                    "category": row.category,
                    "subcategory": row.sub_category or "",
                    "customer_name": getattr(row.customer, "customer_name", "") or "",
                    "contact_no": row.contact_no or "",
                    "location": row.address or "",
                    "ward": getattr(row.ward, "ward_name", "") or "",
                }
            )
        for row in breakdowns:
            assignment = row.trip_assignment_id
            trip_plan = getattr(assignment, "trip_plan_id", None)
            alerts.append(
                {
                    "id": row.unique_id,
                    "kind": "vehicle_breakdown",
                    "title": f"{row.get_breakdown_reason_display()} · {row.breakdown_vehicle_id.vehicle_no}",
                    "status": row.get_status_display(),
                    "severity": "critical" if row.status == VehicleBreakdown.STATUS_REPORTED else "warning",
                    "created": row.created_at.isoformat() if row.created_at else None,
                    "updated": row.updated_at.isoformat() if row.updated_at else None,
                    "priority": "Critical" if row.status == VehicleBreakdown.STATUS_REPORTED else "High",
                    "category": "Vehicle Breakdown",
                    "subcategory": row.get_breakdown_reason_display(),
                    "collection_type": trip_plan.get_collection_type_display() if trip_plan else "",
                    "vehicle": row.breakdown_vehicle_id.vehicle_no,
                    "replacement_vehicle": getattr(row.replacement_vehicle_id, "vehicle_no", "") or "",
                    "location": row.breakdown_location or "",
                    "trip_date": assignment.trip_date.isoformat() if assignment and assignment.trip_date else "",
                    "approval_status": row.get_approval_status_display(),
                    "remarks": row.breakdown_remarks or "",
                }
            )
        alerts.sort(key=lambda item: item.get("created") or "", reverse=True)
        return alerts[:10]

    # ==========================================================
    # RECENT GRIEVANCES
    # ==========================================================

    def _recent_grievances(self, ctx):
        qs = self._scoped(
            Complaint.objects.filter(is_deleted=False).order_by("-created"), self._no_location(ctx)
        )[:10]
        return [
            {
                "id": row.unique_id,
                "title": row.main_category or row.category,
                "status": row.status,
                "priority": row.priority,
                "created": row.created.isoformat() if row.created else None,
            }
            for row in qs
        ]
