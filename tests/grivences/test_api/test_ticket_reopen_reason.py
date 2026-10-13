"""Reopening a complaint ticket requires a reason, stored in the reopen and
status histories for audit."""
import pytest


def _reopen_url(ticket):
    return f"/api/v1/complaint-ticket/tickets/{ticket.unique_id}/reopen/"


@pytest.fixture
def resolved_ticket(db, company, project, ward, zone):
    from app.models.core_modules.complaint_management.masters import (
        ComplaintCategory,
        ComplaintPriority,
        ComplaintStatus,
    )
    from app.models.core_modules.complaint_management.ticket import ComplaintTicket

    category = ComplaintCategory.objects.create(category_code="WASTE", category_name="Waste")
    priority = ComplaintPriority.objects.create(priority_code="HIGH", priority_name="High")
    resolved = ComplaintStatus.objects.create(
        status_code="RESOLVED", status_name="Resolved", allow_reopen=True
    )
    ComplaintStatus.objects.create(status_code="REOPENED", status_name="Reopened")

    return ComplaintTicket.objects.create(
        company_id=company.unique_id,
        project_id=project.unique_id,
        ward_id=ward.unique_id,
        zone_id=zone.unique_id,
        category_id=category.unique_id,
        priority_id=priority.unique_id,
        status_id=resolved.unique_id,
    )


@pytest.mark.django_db
class TestTicketReopenReason:
    def test_reopen_without_reason_is_rejected(self, auth_client, resolved_ticket):
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket

        resp = auth_client.post(_reopen_url(resolved_ticket), {}, format="json")

        assert resp.status_code == 400
        assert "reopen_reason" in resp.json()
        ticket = ComplaintTicket.objects.get(pk=resolved_ticket.pk)
        assert ticket.status_id == resolved_ticket.status_id
        assert ticket.reopened_count == 0

    def test_blank_reason_is_rejected(self, auth_client, resolved_ticket):
        resp = auth_client.post(
            _reopen_url(resolved_ticket), {"reopen_reason": "   "}, format="json"
        )
        assert resp.status_code == 400

    def test_reason_stored_in_reopen_and_status_history(self, auth_client, resolved_ticket):
        from app.models.core_modules.complaint_management.transactions import (
            ComplaintReopenHistory,
            ComplaintStatusHistory,
        )

        resp = auth_client.post(
            _reopen_url(resolved_ticket),
            {"reopen_reason": "  Garbage still not collected  "},
            format="json",
        )

        assert resp.status_code == 200
        history = ComplaintReopenHistory.objects.get(ticket_id=resolved_ticket.unique_id)
        assert history.reopen_reason == "Garbage still not collected"
        status_change = ComplaintStatusHistory.objects.filter(
            ticket_id=resolved_ticket.unique_id
        ).latest("pk")
        assert status_change.remarks == "Garbage still not collected"
