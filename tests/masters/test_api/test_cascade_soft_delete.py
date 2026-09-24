"""Cascading soft-delete: District -> City -> Zone/Ward, through the real
API (so AuditViewSetMixin + BaseMaster.delete() both actually run).
"""
import pytest


@pytest.mark.django_db
class TestDistrictCascadeSoftDelete:
    def test_deleting_district_cascades_through_city_zone_ward(
        self, auth_client, district, city, zone, ward
    ):
        from app.models.masters.city import City
        from app.models.masters.zone import Zone
        from app.models.masters.ward import Ward
        from app.models.masters.district import District

        resp = auth_client.delete(f"/api/v1/masters/districts/{district.unique_id}/")
        assert resp.status_code in (200, 204)

        assert District.objects.get(pk=district.pk).is_deleted is True
        assert City.objects.get(pk=city.pk).is_deleted is True
        assert Zone.objects.get(pk=zone.pk).is_deleted is True
        assert Ward.objects.get(pk=ward.pk).is_deleted is True

    def test_sibling_district_is_untouched(
        self, auth_client, company, project, continent, country, state, district, city, zone, ward
    ):
        from app.models.masters.district import District
        from app.models.masters.city import City

        sibling_district = District.objects.create(
            name="Sibling District",
            continent_id=continent.unique_id,
            country_id=country.unique_id,
            state_id=state.unique_id,
        )
        sibling_city = City.objects.create(
            name="Sibling City",
            continent_id=continent.unique_id,
            country_id=country.unique_id,
            state_id=state.unique_id,
            district_id=sibling_district.unique_id,
            company_id=company.unique_id,
            project_id=project.unique_id,
        )

        resp = auth_client.delete(f"/api/v1/masters/districts/{district.unique_id}/")
        assert resp.status_code in (200, 204)

        assert District.objects.get(pk=sibling_district.pk).is_deleted is False
        assert City.objects.get(pk=sibling_city.pk).is_deleted is False

    def test_delete_writes_audit_log(self, auth_client, district, city, zone, ward):
        from app.utils.common_audit import CommonAudit

        before = CommonAudit.objects.filter(object_id=district.unique_id).count()
        resp = auth_client.delete(f"/api/v1/masters/districts/{district.unique_id}/")
        assert resp.status_code in (200, 204)

        after = CommonAudit.objects.filter(object_id=district.unique_id).count()
        assert after > before


@pytest.mark.django_db
class TestComplaintTicketCascadeOneToOne:
    """The prompt's explicit pitfall: a reverse one-to-one child (feedback)
    returns a single object, not a manager, and must not crash the walk —
    it must still cascade, and must not crash when absent either.
    """

    def _make_ticket(self, company, project, ward, zone):
        from app.models.core_modules.complaint_management.masters import (
            ComplaintCategory,
            ComplaintPriority,
            ComplaintStatus,
        )
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket

        category = ComplaintCategory.objects.create(
            category_code="WASTE", category_name="Waste"
        )
        priority = ComplaintPriority.objects.create(
            priority_code="HIGH", priority_name="High"
        )
        status = ComplaintStatus.objects.create(
            status_code="OPEN", status_name="Open"
        )

        return ComplaintTicket.objects.create(
            company_id=company.unique_id,
            project_id=project.unique_id,
            ward_id=ward.unique_id,
            zone_id=zone.unique_id,
            category_id=category.unique_id,
            priority_id=priority.unique_id,
            status_id=status.unique_id,
        )

    def test_ticket_with_one_to_one_feedback_cascades(
        self, auth_client, company, project, ward, zone
    ):
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket
        from app.models.core_modules.complaint_management.transactions import ComplaintFeedback

        ticket = self._make_ticket(company, project, ward, zone)
        feedback = ComplaintFeedback.objects.create(ticket_id=ticket.unique_id, rating=5)

        resp = auth_client.delete(
            f"/api/v1/complaint-ticket/tickets/{ticket.unique_id}/"
        )
        assert resp.status_code in (200, 204)

        assert ComplaintTicket.objects.get(pk=ticket.pk).is_deleted is True
        assert ComplaintFeedback.objects.get(pk=feedback.pk).is_deleted is True

    def test_ticket_with_no_one_to_one_children_does_not_crash(
        self, auth_client, company, project, ward, zone
    ):
        """A ticket with nothing linked to its reverse one-to-ones must not
        raise DoesNotExist while walking the cascade graph."""
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket

        ticket = self._make_ticket(company, project, ward, zone)

        resp = auth_client.delete(
            f"/api/v1/complaint-ticket/tickets/{ticket.unique_id}/"
        )
        assert resp.status_code in (200, 204)
        assert ComplaintTicket.objects.get(pk=ticket.pk).is_deleted is True
