"""Supervisor-facing attendance summary — present/absent/leave counts + staff
lists for a date range, backed by the same `Recognized` punch records
`AttendanceListViewSet` uses.

There is no leave-tracking model in this project, so `leave_count`/
`leave_staff` are always empty; every staff member who didn't punch in the
range counts as absent. Staff scope matches `staff-creations/staffcreation/`
(company-scoped via `CompanyScopedViewSet`) — no additional zone/team filter.
"""

from django.utils.dateparse import parse_date
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from app.models.staff_creations.staffcreation import Staffcreation
from app.models.staff_creations.attendance import Recognized
from app.serializers.superadmin.staff_management.staffcreation_serializer import (
    StaffcreationSerializer,
)
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class AttendanceRecordsViewSet(CompanyScopedViewSet):
    """GET /api/v1/attendance/records/?from_date=&to_date="""

    queryset = Staffcreation.objects.filter(is_deleted=False)
    serializer_class = StaffcreationSerializer

    @staticmethod
    def _date_range(request):
        today = timezone.localdate()
        from_date = parse_date(request.query_params.get("from_date", "")) or today
        to_date = parse_date(request.query_params.get("to_date", "")) or today
        if from_date > to_date:
            raise ValidationError({"to_date": "to_date must be on or after from_date"})
        return from_date, to_date

    def list(self, request, *args, **kwargs):
        from_date, to_date = self._date_range(request)

        staff_qs = self.filter_queryset(self.get_queryset()).select_related(
            "designation_id", "department_id", "staffusertype_id", "personal_details",
        )

        present_ids = self._present_staff_ids(staff_qs, from_date, to_date)

        present, absent = [], []
        for staff in staff_qs:
            bucket = present if staff.staff_unique_id in present_ids else absent
            bucket.append(staff)

        def _serialize(rows, status_label):
            data = StaffcreationSerializer(rows, many=True, context={"request": request}).data
            for row in data:
                row["attendance_status"] = status_label
            return data

        return Response({
            "staff_summary": {
                "present_count": len(present),
                "absent_count": len(absent),
                "leave_count": 0,
                "present_staff": _serialize(present, "present"),
                "absent_staff": _serialize(absent, "absent"),
                "leave_staff": [],
            }
        })

    @staticmethod
    def _present_staff_ids(staff_qs, from_date, to_date):
        """A staff member is "present" for the range if they have at least
        one IN and one OUT punch on the SAME day, on any day in range."""
        # MySQL rejects `IN (<subquery with LIMIT>)`, which `staff__in=staff_qs`
        # would produce if the caller passed a sliced/limited queryset — so
        # materialize the ids first rather than filtering on the queryset itself.
        staff_ids = list(staff_qs.values_list("staff_unique_id", flat=True))
        records = Recognized.objects.filter(
            staff_id__in=staff_ids,
            recognition_date__range=(from_date, to_date),
        ).values("staff__staff_unique_id", "recognition_date", "punch_type")

        by_day = {}
        for row in records:
            key = (row["staff__staff_unique_id"], row["recognition_date"])
            by_day.setdefault(key, set()).add(row["punch_type"])

        present_ids = set()
        for (staff_id, _day), punch_types in by_day.items():
            if "IN" in punch_types and "OUT" in punch_types:
                present_ids.add(staff_id)
        return present_ids
