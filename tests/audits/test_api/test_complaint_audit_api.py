"""Complaint Audit: per-ticket lifecycle summary and timeline built from the
ticket workflow's own history rows."""
from datetime import timedelta

import pytest

BASE = "/api/v1/audits/complaint-audit/"


@pytest.fixture
def statuses(db):
    from app.models.core_modules.complaint_management.masters import ComplaintStatus

    def make(code, name, **extra):
        return ComplaintStatus.objects.create(status_code=code, status_name=name, **extra)

    return {
        "SUBMITTED": make("SUBMITTED", "Submitted", sort_order=10),
        "IN_PROGRESS": make("IN_PROGRESS", "In Progress", sort_order=20),
        "RESOLVED": make("RESOLVED", "Resolved", allow_reopen=True, sort_order=30),
        "REOPENED": make("REOPENED", "Reopened", sort_order=40),
        "ESCALATED": make("ESCALATED", "Escalated", sort_order=50),
    }


@pytest.fixture
def audited_ticket(db, company, project, ward, zone, statuses):
    """A ticket that was raised, worked, resolved, reopened, escalated and
    resolved again — with history timestamps spread over three days."""
    from django.utils import timezone

    from app.models.core_modules.complaint_management.masters import (
        ComplaintCategory,
        ComplaintPriority,
    )
    from app.models.core_modules.complaint_management.ticket import ComplaintTicket
    from app.models.core_modules.complaint_management.transactions import (
        ComplaintEscalationHistory,
        ComplaintReopenHistory,
        ComplaintStatusHistory,
    )

    category = ComplaintCategory.objects.create(category_code="WASTE", category_name="Waste")
    priority = ComplaintPriority.objects.create(priority_code="HIGH", priority_name="High")
    ticket = ComplaintTicket.objects.create(
        company_id=company.unique_id,
        project_id=project.unique_id,
        ward_id=ward.unique_id,
        zone_id=zone.unique_id,
        category_id=category.unique_id,
        priority_id=priority.unique_id,
        status_id=statuses["RESOLVED"].unique_id,
        title="Bin overflowing",
        description="Bin near market overflowing",
        profile_name="Ravi",
    )
    start = timezone.now() - timedelta(days=3)
    ComplaintTicket.objects.filter(pk=ticket.pk).update(
        created=start,
        reopened_count=1,
        resolved_at=start + timedelta(days=2),
    )

    def history(at, from_code, to_code, remarks, **extra):
        row = ComplaintStatusHistory.objects.create(
            ticket_id=ticket.unique_id,
            from_status_id=statuses[from_code].unique_id if from_code else None,
            to_status_id=statuses[to_code].unique_id,
            remarks=remarks,
            **extra,
        )
        ComplaintStatusHistory.objects.filter(pk=row.pk).update(changed_at=at)

    history(start, None, "SUBMITTED", "Ticket created", changed_by_system=True)
    history(start + timedelta(hours=2), "SUBMITTED", "IN_PROGRESS", "Team dispatched")
    history(start + timedelta(hours=10), "IN_PROGRESS", "RESOLVED", "Bin emptied")
    history(start + timedelta(days=1), "RESOLVED", "REOPENED", "Bin full again next day")
    history(start + timedelta(days=1, hours=1), "REOPENED", "ESCALATED", "Auto-escalated L1 -> L2")
    history(start + timedelta(days=2), "ESCALATED", "RESOLVED", "Extra bin installed")

    reopen = ComplaintReopenHistory.objects.create(
        ticket_id=ticket.unique_id,
        reopen_reason="Bin full again next day",
        previous_status_id=statuses["RESOLVED"].unique_id,
    )
    ComplaintReopenHistory.objects.filter(pk=reopen.pk).update(reopened_at=start + timedelta(days=1))
    escalation = ComplaintEscalationHistory.objects.create(
        ticket_id=ticket.unique_id,
        escalation_level=2,
        reason="SLA breached",
        escalated_by_system=True,
    )
    ComplaintEscalationHistory.objects.filter(pk=escalation.pk).update(
        escalated_at=start + timedelta(days=1, hours=1)
    )
    ticket.refresh_from_db()
    return ticket


@pytest.mark.django_db
class TestComplaintAuditList:
    def test_summary_has_remarks_counts_and_timings(self, auth_client, audited_ticket):
        resp = auth_client.get(BASE)

        assert resp.status_code == 200
        row = next(r for r in resp.json()["results"] if r["unique_id"] == audited_ticket.unique_id)
        assert row["status_code"] == "RESOLVED"
        # Latest resolution wins over the first one.
        assert row["resolution_remarks"] == "Extra bin installed"
        assert row["last_reopen_reason"] == "Bin full again next day"
        assert row["reopen_count"] == 1
        assert row["escalation_count"] == 1
        assert row["max_escalation_level"] == 2
        assert row["auto_escalation_count"] == 1
        assert row["first_resolution_seconds"] == 10 * 3600
        assert row["total_resolution_seconds"] == 2 * 86400
        assert row["open_seconds"] is None

    def test_filters(self, auth_client, audited_ticket):
        ids = lambda resp: {r["unique_id"] for r in resp.json()["results"]}  # noqa: E731

        assert audited_ticket.unique_id in ids(auth_client.get(BASE, {"reopened": "1"}))
        assert audited_ticket.unique_id in ids(auth_client.get(BASE, {"escalated": "1"}))
        assert audited_ticket.unique_id not in ids(auth_client.get(BASE, {"status": "SUBMITTED"}))
        assert audited_ticket.unique_id in ids(auth_client.get(BASE, {"search": "overflowing"}))

    def test_paginated(self, auth_client, audited_ticket):
        resp = auth_client.get(BASE, {"limit": 10})
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1


@pytest.mark.django_db
class TestComplaintAuditDetail:
    def test_timeline_events_in_order_without_duplicates(self, auth_client, audited_ticket):
        resp = auth_client.get(f"{BASE}{audited_ticket.unique_id}/")

        assert resp.status_code == 200
        body = resp.json()
        types = [e["type"] for e in body["timeline"]]
        # The REOPENED / ESCALATED status rows are represented by the richer
        # reopen and escalation events, not listed twice.
        assert types == [
            "CREATED",
            "STATUS_CHANGED",
            "RESOLVED",
            "REOPENED",
            "ESCALATED",
            "RESOLVED",
        ]
        reopen = body["timeline"][3]
        assert reopen["remarks"] == "Bin full again next day"
        assert reopen["elapsed_seconds"] == 86400
        escalation = body["timeline"][4]
        assert escalation["details"]["automatic"] is True
        assert escalation["actor_name"] == "System"
        assert escalation["remarks"] == "SLA breached"

    def test_status_durations(self, auth_client, audited_ticket):
        body = auth_client.get(f"{BASE}{audited_ticket.unique_id}/").json()
        durations = {d["status_code"]: d for d in body["status_durations"]}

        assert durations["SUBMITTED"]["seconds"] == 2 * 3600
        assert durations["IN_PROGRESS"]["seconds"] == 8 * 3600
        # Resolved once before the reopen (10h -> 1 day); the final
        # resolution is the end state and is not counted.
        assert durations["RESOLVED"]["seconds"] == 14 * 3600
        assert durations["RESOLVED"]["times_entered"] == 1

    def test_deleted_ticket_shows_delete_reason(self, auth_client, audited_ticket):
        auth_client.delete(
            f"/api/v1/complaint-ticket/tickets/{audited_ticket.unique_id}/",
            {"delete_reason": "Duplicate complaint"},
            format="json",
        )

        body = auth_client.get(f"{BASE}{audited_ticket.unique_id}/").json()

        assert body["is_deleted"] is True
        assert body["delete_reason"] == "Duplicate complaint"
        assert body["timeline"][-1]["type"] == "DELETED"
        assert body["timeline"][-1]["remarks"] == "Duplicate complaint"


    def test_unaudited_delete_has_no_time_and_sorts_last(self, auth_client, audited_ticket):
        """A ticket deleted before deletes were audited has no CommonAudit
        row; its Deleted event must not borrow a made-up time (which put it
        before later events) but come last with time unknown."""
        audited_ticket.delete()

        body = auth_client.get(f"{BASE}{audited_ticket.unique_id}/").json()

        last = body["timeline"][-1]
        assert last["type"] == "DELETED"
        assert last["at"] is None
        assert last["elapsed_seconds"] is None


@pytest.mark.django_db
class TestStaffActorRecorded:
    def test_reopen_by_staff_records_staff_id(self, api_client, audited_ticket, statuses):
        """Staff log in as StaffcreationOfficeDetails, not an auth User; their
        reopen must still be attributed in the history."""
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket
        from app.models.core_modules.complaint_management.transactions import (
            ComplaintReopenHistory,
        )
        from app.viewsets.core_modules.complaint_management.ticket_viewset import _actor_staff_id

        class StaffUser:
            staff_unique_id = "STAFF-1"
            is_authenticated = True

        class Request:
            user = StaffUser()

        assert _actor_staff_id(Request()) == "STAFF-1"
        assert ComplaintReopenHistory._meta.get_field("reopened_by_staff_id")
        assert ComplaintTicket.objects.filter(pk=audited_ticket.pk).exists()
