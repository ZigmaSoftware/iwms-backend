"""GET /schedule-operations/daily-trip-logs/summary/ — list-page KPIs."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog

URL = "/api/v1/schedule-operations/daily-trip-logs/summary/"


@pytest.fixture
def logs(db, company, project):
    today = timezone.localdate()
    base = {"company_id": company.unique_id, "project_id": project.unique_id}
    # bulk_create skips DailyTripLog.save()'s assignment autofill, which these
    # aggregate-only rows don't need.
    return DailyTripLog.objects.bulk_create([
        DailyTripLog(
            unique_id="DTL-SUM-1", **base, trip_assignment_id="DTA-1", trip_date=today,
            collected_weight_kg=Decimal("10.50"), household_collected_weight_kg=Decimal("2.00"),
            log_status=DailyTripLog.LOG_STATUS_VERIFIED,
        ),
        DailyTripLog(
            unique_id="DTL-SUM-2", **base, trip_assignment_id="DTA-1", trip_date=today,
            collected_weight_kg=Decimal("4.00"),
            log_status=DailyTripLog.LOG_STATUS_UNVERIFIED,
        ),
        DailyTripLog(
            unique_id="DTL-SUM-3", **base, trip_assignment_id="DTA-2", trip_date=date_days_ago(3),
            collected_weight_kg=Decimal("20.00"),
            log_status=DailyTripLog.LOG_STATUS_UNVERIFIED,
        ),
    ])


def date_days_ago(days):
    return timezone.localdate() - timedelta(days=days)


@pytest.mark.django_db
class TestDailyTripLogSummary:
    def test_totals_over_all_matching_logs(self, auth_client, logs, company, project):
        resp = auth_client.get(URL, {"company_id": company.unique_id, "project_id": project.unique_id})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_logs"] == 3
        assert body["trips"] == 2
        assert body["bin_weight_kg"] == 34.5
        assert body["household_weight_kg"] == 2.0
        assert body["total_weight_kg"] == 36.5
        assert body["today_weight_kg"] == 16.5
        assert body["status_counts"] == {"Unverified": 2, "Verified": 1}

    def test_respects_list_filters(self, auth_client, logs, company, project):
        resp = auth_client.get(URL, {
            "company_id": company.unique_id,
            "project_id": project.unique_id,
            "date": str(timezone.localdate()),
        })
        body = resp.json()
        assert body["total_logs"] == 2
        assert body["status_counts"] == {"Unverified": 1, "Verified": 1}
