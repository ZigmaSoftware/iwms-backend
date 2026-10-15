from datetime import timedelta

import pytest
from django.utils import timezone

from app.models.core_modules.daily_operations.trip_retrip_request import (
    TripRetripRequest,
)
from app.services.retrip_timeout_service import process_retrip_timeouts
from app.services import retrip_service


pytestmark = pytest.mark.django_db


def _pending_request(*, age_minutes):
    request = TripRetripRequest.objects.create(
        assignment_id="DTA-TIMEOUT-TEST",
        reason="Shift ending",
        status=TripRetripRequest.STATUS_PENDING,
    )
    created_at = timezone.now() - timedelta(minutes=age_minutes)
    TripRetripRequest.objects.filter(pk=request.pk).update(
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=30),
    )
    request.refresh_from_db()
    return request


def test_retrip_reminder_is_sent_only_once(monkeypatch):
    request = _pending_request(age_minutes=11)
    sent = []
    monkeypatch.setattr(
        "app.services.retrip_timeout_service._notify",
        lambda *args, **kwargs: sent.append(args[1]),
    )

    first = process_retrip_timeouts()
    second = process_retrip_timeouts()

    request.refresh_from_db()
    assert first == {"reminded": 1, "escalated": 0, "expired": 0}
    assert second == {"reminded": 0, "escalated": 0, "expired": 0}
    assert request.reminder_sent_at is not None
    assert len(sent) == 1


def test_retrip_escalation_does_not_repeat(monkeypatch):
    request = _pending_request(age_minutes=21)
    sent = []
    monkeypatch.setattr(
        "app.services.retrip_timeout_service._notify",
        lambda *args, **kwargs: sent.append(args[1]),
    )

    first = process_retrip_timeouts()
    second = process_retrip_timeouts()

    request.refresh_from_db()
    assert first == {"reminded": 0, "escalated": 1, "expired": 0}
    assert second == {"reminded": 0, "escalated": 0, "expired": 0}
    assert request.reminder_sent_at is not None
    assert request.escalated_at is not None
    assert len(sent) == 1


def test_retrip_expires_and_no_longer_counts_as_pending(monkeypatch):
    request = _pending_request(age_minutes=31)
    monkeypatch.setattr(
        "app.services.retrip_timeout_service._notify", lambda *args, **kwargs: None
    )

    result = process_retrip_timeouts()

    request.refresh_from_db()
    assert result == {"reminded": 0, "escalated": 0, "expired": 1}
    assert request.status == TripRetripRequest.STATUS_EXPIRED
    assert request.reviewed_at is not None
    assert "Expired automatically" in request.review_remarks
    assert not TripRetripRequest.objects.filter(
        pk=request.pk, status=TripRetripRequest.STATUS_PENDING
    ).exists()


def test_approval_attempt_commits_expiry_instead_of_creating_trip(monkeypatch):
    request = _pending_request(age_minutes=31)
    monkeypatch.setattr(
        "app.services.retrip_timeout_service._notify", lambda *args, **kwargs: None
    )

    continuation = retrip_service.approve_retrip(request, reviewed_by=None)

    request.refresh_from_db()
    assert continuation is None
    assert request.status == TripRetripRequest.STATUS_EXPIRED
