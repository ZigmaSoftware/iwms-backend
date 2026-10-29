"""API tests for VehicleCreation RC / insurance document history."""
from datetime import date

import pytest

from app.models.masters.transport_masters.vehicleCreation import (
    VehicleCreation,
    VehicleDocumentHistory,
)

BASE = "/api/v1/transport-masters/vehicle-creation/"


@pytest.fixture
def vehicle(db, company, project):
    return VehicleCreation.objects.create(
        company_id=company.unique_id,
        project_id=project.unique_id,
        vehicle_no="TN-09-DH-1001",
        vehicle_insurance="POL-OLD",
        insurance_expiry_date=date(2026, 1, 31),
    )


@pytest.mark.django_db
class TestVehicleDocumentHistory:
    def test_insurance_renewal_is_recorded(self, auth_client, vehicle):
        resp = auth_client.patch(
            f"{BASE}{vehicle.unique_id}/",
            {"vehicle_insurance": "POL-NEW", "insurance_expiry_date": "2027-01-31"},
            format="json",
        )
        assert resp.status_code in (200, 204)

        rows = list(VehicleDocumentHistory.objects.filter(vehicle_id=vehicle.unique_id))
        assert len(rows) == 1
        row = rows[0]
        assert row.document_type == VehicleDocumentHistory.DocumentType.INSURANCE
        assert row.previous_document_number == "POL-OLD"
        assert row.new_document_number == "POL-NEW"
        assert row.previous_expiry_date == date(2026, 1, 31)
        assert row.new_expiry_date == date(2027, 1, 31)

    def test_rc_expiry_change_is_recorded(self, auth_client, vehicle):
        auth_client.patch(
            f"{BASE}{vehicle.unique_id}/", {"rc_expiry_date": "2030-05-01"}, format="json"
        )
        row = VehicleDocumentHistory.objects.get(vehicle_id=vehicle.unique_id)
        assert row.document_type == VehicleDocumentHistory.DocumentType.RC
        assert row.new_expiry_date == date(2030, 5, 1)

    def test_non_document_edit_records_nothing(self, auth_client, vehicle):
        auth_client.patch(
            f"{BASE}{vehicle.unique_id}/", {"vehicle_condition": "SECOND_HAND"}, format="json"
        )
        assert not VehicleDocumentHistory.objects.filter(vehicle_id=vehicle.unique_id).exists()

    def test_document_history_endpoint_lists_and_filters(self, auth_client, vehicle):
        auth_client.patch(
            f"{BASE}{vehicle.unique_id}/",
            {"vehicle_insurance": "POL-NEW", "rc_expiry_date": "2030-05-01"},
            format="json",
        )

        resp = auth_client.get(f"{BASE}{vehicle.unique_id}/document-history/")
        assert resp.status_code == 200
        assert {r["document_type"] for r in resp.json()} == {"RC", "INSURANCE"}

        resp = auth_client.get(
            f"{BASE}{vehicle.unique_id}/document-history/", {"document_type": "insurance"}
        )
        assert [r["document_type"] for r in resp.json()] == ["INSURANCE"]
