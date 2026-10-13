"""Delete reason: required on every DELETE, stored on the deleted row, on
every cascaded child, and on the CommonAudit entry."""
import pytest

DISTRICTS = "/api/v1/masters/districts/"


@pytest.mark.django_db
class TestDeleteReason:
    def test_delete_without_reason_is_rejected(self, auth_client, district):
        from app.models.masters.district import District

        resp = auth_client.delete(f"{DISTRICTS}{district.unique_id}/")

        assert resp.status_code == 400
        assert "delete_reason" in resp.json()
        assert District.objects.get(pk=district.pk).is_deleted is False

    def test_blank_reason_is_rejected(self, auth_client, district):
        resp = auth_client.delete(
            f"{DISTRICTS}{district.unique_id}/", {"delete_reason": "   "}, format="json"
        )
        assert resp.status_code == 400

    def test_reason_stored_on_row_and_cascaded_children(
        self, auth_client, district, city, zone, ward
    ):
        from app.models.masters.city import City
        from app.models.masters.district import District
        from app.models.masters.ward import Ward

        resp = auth_client.delete(
            f"{DISTRICTS}{district.unique_id}/",
            {"delete_reason": "Duplicate entry"},
            format="json",
        )
        assert resp.status_code in (200, 204)

        assert District.objects.get(pk=district.pk).delete_reason == "Duplicate entry"
        child_reason = City.objects.get(pk=city.pk).delete_reason
        assert child_reason.startswith("Duplicate entry")
        assert district.unique_id in child_reason
        assert Ward.objects.get(pk=ward.pk).delete_reason.startswith("Duplicate entry")

    def test_reason_stored_on_audit_entry(self, auth_client, district):
        from app.utils.common_audit import CommonAudit

        auth_client.delete(
            f"{DISTRICTS}{district.unique_id}/",
            {"delete_reason": "Created by mistake"},
            format="json",
        )

        audit = CommonAudit.objects.filter(
            object_id=district.unique_id, method="DELETE"
        ).latest("createdAt")
        assert audit.delete_reason == "Created by mistake"

    def test_reason_accepted_as_query_param(self, auth_client, district):
        from app.models.masters.district import District

        resp = auth_client.delete(
            f"{DISTRICTS}{district.unique_id}/?delete_reason=Merged"
        )
        assert resp.status_code in (200, 204)
        assert District.objects.get(pk=district.pk).delete_reason == "Merged"
