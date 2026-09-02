"""
District Dashboard API
Authenticated-only endpoint — no module permission check.
Data source: DailyTripLog (Submitted + Verified logs only)
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.staff_creations.staffcreation import Staffcreation

ZERO = Decimal("0")
TWO = Decimal("0.01")


def _r(value):
    if value is None:
        return ZERO
    return Decimal(str(value)).quantize(TWO, rounding=ROUND_HALF_UP)


def _pct(num, den):
    d = Decimal(str(den)) if den is not None else ZERO
    if d == ZERO:
        return ZERO
    return _r(Decimal(str(num)) / d * Decimal("100"))


def _var_pct(actual, agreed):
    a = Decimal(str(agreed)) if agreed is not None else ZERO
    if a == ZERO:
        return ZERO
    return _r((Decimal(str(actual)) - a) / a * Decimal("100"))


def _status(actual, agreed):
    a, g = Decimal(str(actual)), Decimal(str(agreed))
    if a > g:
        return "Surplus"
    if a < g:
        return "Deficit"
    return "On Target"


class DistrictDashboardViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    def _get_staff(self, request):
        user = request.user
        if getattr(user, "district_id", None) is not None:
            return user
        staff_record = getattr(user, "staff_id", None)
        if isinstance(staff_record, Staffcreation):
            return staff_record
        return None

    def _get_district(self, request):
        staff = self._get_staff(request)
        if staff:
            return getattr(staff, "district_id", None)
        return None

    def list(self, request):
        district = self._get_district(request)
        if not district:
            return Response(
                {"detail": "District not found for this user."},
                status=403,
            )

        district_uid = district.unique_id
        district_name = getattr(district, "name", "") or ""
        month = request.query_params.get("month", "")
        from_date = request.query_params.get("from_date", "")
        to_date = request.query_params.get("to_date", "")
        sort = request.query_params.get("sort", "absolute").lower()

        base_qs = DailyTripLog.objects.filter(
            panchayat_id__district_id=district_uid,
            is_deleted=False,
        ).select_related("waste_type_id", "collection_point_id", "panchayat_id")

        monthly_data = self._monthly_report(base_qs, district, month, sort)
        daily_data = self._daily_data(base_qs, month, from_date, to_date)

        return Response(
            {
                "district_name": district_name,
                "results": monthly_data["results"],
                "monthly_trends": monthly_data["monthly_trends"],
                "waste_type_breakdown": monthly_data["waste_type_breakdown"],
                "kpis": monthly_data["kpis"],
                "day_wise_collection": daily_data["day_wise"],
                "trip_waste_types": daily_data["waste_types"],
                "day_wise_breakdown": daily_data["day_wise_breakdown"],
                "daily_rows": daily_data["daily_rows"],
                "daily_kpis": daily_data["daily_kpis"],
            }
        )

    def _monthly_report(self, base_qs, district, month, sort):
        qs = base_qs
        if month:
            try:
                year, mon = month.split("-")
                qs = qs.filter(
                    trip_date__year=int(year),
                    trip_date__month=int(mon),
                )
            except ValueError:
                pass

        grouped = qs.values(
            "trip_date__year",
            "trip_date__month",
            "waste_type_id",
            "waste_type_id__waste_type_name",
            "panchayat_id__agreed_weight_kg",
        ).annotate(
            total_actual_weight=Sum("collected_weight_kg"),
            total_trips=Count("unique_id"),
            collection_points=Count("collection_point_id", distinct=True),
            distinct_trip_days=Count("trip_date", distinct=True),
        )

        rows_map = {}
        for row in grouped:
            year_val = row["trip_date__year"]
            month_val = row["trip_date__month"]
            month_str = f"{year_val}-{month_val:02d}"
            waste_type = row["waste_type_id__waste_type_name"] or "—"
            key = (month_str, waste_type)

            actual = Decimal(str(row["total_actual_weight"] or 0))
            agreed_per_day = Decimal(str(row.get("panchayat_id__agreed_weight_kg") or 0))
            trip_days = int(row["distinct_trip_days"] or 0)
            agreed = agreed_per_day * Decimal(str(trip_days))
            var = actual - agreed
            trips = int(row["total_trips"] or 0)
            points = int(row["collection_points"] or 0)

            if key not in rows_map:
                rows_map[key] = {
                    "unique_id": f"DIST-{month_str}-{waste_type}",
                    "month": month_str,
                    "district_id": district.unique_id,
                    "district_name": getattr(district, "name", "") or "",
                    "waste_type": waste_type,
                    "total_agreed_weight": float(_r(agreed)),
                    "total_actual_weight": float(_r(actual)),
                    "variance_kg": float(_r(var)),
                    "variance_percent": float(_var_pct(actual, agreed)),
                    "report_status": _status(actual, agreed),
                    "total_trips": trips,
                    "collection_points_covered": points,
                    "collection_efficiency_percent": float(_pct(actual, agreed)),
                    "coverage_efficiency_percent": float(_pct(points, trips)),
                    "average_weight_per_trip": float(_r(actual / Decimal(trips)) if trips else ZERO),
                }
            else:
                existing = rows_map[key]
                existing["total_actual_weight"] = float(_r(Decimal(str(existing["total_actual_weight"])) + actual))
                existing["total_agreed_weight"] = float(_r(Decimal(str(existing["total_agreed_weight"])) + agreed))
                existing["variance_kg"] = float(_r(Decimal(str(existing["variance_kg"])) + var))
                existing["total_trips"] += trips
                existing["collection_points_covered"] += points
                existing["collection_efficiency_percent"] = float(_pct(
                    Decimal(str(existing["total_actual_weight"])),
                    Decimal(str(existing["total_agreed_weight"]))
                ))
                existing["coverage_efficiency_percent"] = float(_pct(
                    Decimal(str(existing["collection_points_covered"])),
                    Decimal(str(existing["total_trips"]))
                ))
                existing["average_weight_per_trip"] = float(_r(
                    Decimal(str(existing["total_actual_weight"])) / Decimal(existing["total_trips"]) if existing["total_trips"] else ZERO
                ))
                existing["variance_percent"] = float(_var_pct(
                    Decimal(str(existing["total_actual_weight"])),
                    Decimal(str(existing["total_agreed_weight"]))
                ))
                existing["report_status"] = _status(
                    Decimal(str(existing["total_actual_weight"])),
                    Decimal(str(existing["total_agreed_weight"]))
                )

        rows = list(rows_map.values())
        if sort == "deficit":
            rows.sort(key=lambda r: r["variance_kg"])
        elif sort == "surplus":
            rows.sort(key=lambda r: r["variance_kg"], reverse=True)
        else:
            rows.sort(key=lambda r: abs(r["variance_kg"]), reverse=True)

        return {
            "results": rows,
            "monthly_trends": self._monthly_trends(rows),
            "waste_type_breakdown": self._waste_breakdown(rows),
            "kpis": self._totals(rows),
        }

    def _monthly_trends(self, rows):
        t = {}
        for r in rows:
            m = r["month"]
            t.setdefault(m, {
                "month": m,
                "total_agreed_weight": 0,
                "total_actual_weight": 0,
                "variance_kg": 0,
                "total_trips": 0,
                "collection_points_covered": 0,
            })
            t[m]["total_agreed_weight"] += r["total_agreed_weight"]
            t[m]["total_actual_weight"] += r["total_actual_weight"]
            t[m]["variance_kg"] += r["variance_kg"]
            t[m]["total_trips"] += r["total_trips"]
            t[m]["collection_points_covered"] += r["collection_points_covered"]
        return sorted(t.values(), key=lambda x: str(x["month"]))

    def _waste_breakdown(self, rows):
        t = {}
        for r in rows:
            wt = r["waste_type"] or "Unknown"
            t.setdefault(wt, {
                "waste_type": wt,
                "total_agreed_weight": 0,
                "total_actual_weight": 0,
                "variance_kg": 0,
            })
            t[wt]["total_agreed_weight"] += r["total_agreed_weight"]
            t[wt]["total_actual_weight"] += r["total_actual_weight"]
            t[wt]["variance_kg"] += r["variance_kg"]
        return sorted(t.values(), key=lambda x: abs(x["variance_kg"]), reverse=True)

    def _totals(self, rows):
        agreed = sum(Decimal(str(r["total_agreed_weight"])) for r in rows)
        actual = sum(Decimal(str(r["total_actual_weight"])) for r in rows)
        trips = sum(r["total_trips"] for r in rows)
        points = sum(r["collection_points_covered"] for r in rows)
        return {
            "total_agreed_weight": float(_r(agreed)),
            "total_actual_weight": float(_r(actual)),
            "variance_kg": float(_r(actual - agreed)),
            "collection_efficiency_percent": float(_pct(actual, agreed)),
            "average_weight_per_trip": float(_r(actual / Decimal(trips)) if trips else ZERO),
            "coverage_efficiency_percent": float(_pct(points, trips)),
            "total_trips": trips,
            "collection_points_covered": points,
            "report_status": _status(actual, agreed),
        }

    def _daily_data(self, base_qs, month, from_date="", to_date=""):
        qs = base_qs
        if month:
            try:
                year, mon = month.split("-")
                qs = qs.filter(
                    trip_date__year=int(year),
                    trip_date__month=int(mon),
                )
            except ValueError:
                pass

        if from_date:
            qs = qs.filter(trip_date__gte=from_date)
        if to_date:
            qs = qs.filter(trip_date__lte=to_date)

        agreed_by_date = {}
        for row in qs.values("trip_date", "panchayat_id__agreed_weight_kg").distinct():
            date = row.get("trip_date")
            if date is None:
                continue
            agreed_by_date[date] = agreed_by_date.get(date, ZERO) + Decimal(str(row.get("panchayat_id__agreed_weight_kg") or 0))

        breakdown_raw = (
            qs.values("trip_date", "waste_type_id__waste_type_name")
            .annotate(
                actual_weight_kg=Sum("collected_weight_kg"),
                trip_count=Count("unique_id"),
                points_covered=Count("collection_point_id", distinct=True),
            )
            .order_by("trip_date", "waste_type_id__waste_type_name")
        )

        day_wise_breakdown = [
            {
                "date": str(r["trip_date"]),
                "waste_type": r["waste_type_id__waste_type_name"] or "Unknown",
                "actual_weight_kg": float(_r(r["actual_weight_kg"] or 0)),
                "agreed_weight_kg": float(_r(agreed_by_date.get(r["trip_date"], ZERO))),
                "trip_count": int(r["trip_count"] or 0),
                "points_covered": int(r["points_covered"] or 0),
            }
            for r in breakdown_raw
        ]

        daily_rows = [
            {
                "unique_id": f"DIST-D-{r['trip_date']}-{waste_type}",
                "date": str(r["trip_date"]),
                "waste_type": waste_type,
                "agreed_weight_kg": float(_r(agreed_by_date.get(r["trip_date"], ZERO))),
                "actual_weight_kg": float(_r(r["actual_weight_kg"] or 0)),
                "variance_kg": float(_r(Decimal(str(r["actual_weight_kg"] or 0)) - _r(agreed_by_date.get(r["trip_date"], ZERO)))),
                "variance_percent": float(_var_pct(r["actual_weight_kg"] or 0, agreed_by_date.get(r["trip_date"], ZERO))),
                "report_status": _status(r["actual_weight_kg"] or 0, agreed_by_date.get(r["trip_date"], ZERO)),
                "total_trips": int(r["trip_count"] or 0),
                "collection_points_covered": int(r["points_covered"] or 0),
            }
            for r in breakdown_raw
            for waste_type in [r["waste_type_id__waste_type_name"] or "—"]
        ]

        total_agreed = sum(agreed_by_date.values())
        total_actual = sum(Decimal(str(r["actual_weight_kg"] or 0)) for r in breakdown_raw)
        total_trips = sum(int(r["trip_count"] or 0) for r in breakdown_raw)
        total_points = sum(int(r["points_covered"] or 0) for r in breakdown_raw)

        daily_kpis = {
            "total_actual_kg": float(_r(total_actual)),
            "total_agreed_kg": float(_r(total_agreed)),
            "variance_kg": float(_r(total_actual - total_agreed)),
            "collection_efficiency_percent": float(_pct(total_actual, total_agreed)),
            "total_trips": total_trips,
            "collection_points_covered": total_points,
        }

        trip_waste_types = [
            {
                "waste_type": r["waste_type_id__waste_type_name"] or "Unknown",
                "collected_weight_kg": float(_r(r["actual_weight_kg"] or 0)),
                "trip_count": int(r["trip_count"] or 0),
            }
            for r in qs.values("waste_type_id__waste_type_name").annotate(
                actual_weight_kg=Sum("collected_weight_kg"),
                trip_count=Count("unique_id"),
            )
        ]

        day_wise = [
            {
                "date": str(r["trip_date"]),
                "collected_weight_kg": float(_r(r["collected_weight_kg"] or 0)),
                "trip_count": int(r["trip_count"] or 0),
            }
            for r in qs.values("trip_date").annotate(
                collected_weight_kg=Sum("collected_weight_kg"),
                trip_count=Count("unique_id"),
            ).order_by("trip_date")
        ]

        return {
            "day_wise": day_wise,
            "waste_types": trip_waste_types,
            "day_wise_breakdown": day_wise_breakdown,
            "daily_rows": daily_rows,
            "daily_kpis": daily_kpis,
        }
