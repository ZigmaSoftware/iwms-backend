"""Cascading soft-delete from the top of the tenancy hierarchy:
Company -> Project -> District (geo chain) and Company/Project -> Department
(a direct, non-geo child), through the real API so AuditViewSetMixin +
BaseMaster.delete() both actually run.
"""
import pytest


@pytest.mark.django_db
class TestCompanyCascadeSoftDelete:
    def test_deleting_company_cascades_through_project_and_district(
        self, auth_client, company, project, continent, country, state
    ):
        from app.models.superadmin_masters.company import Company
        from app.models.superadmin_masters.project import Project
        from app.models.masters.district import District

        district = District.objects.create(
            name="Cascade District",
            continent_id=continent.unique_id,
            country_id=country.unique_id,
            state_id=state.unique_id,
            company_id=company.unique_id,
            project_id=project.unique_id,
        )

        resp = auth_client.delete(f"/api/v1/superadmin/company/{company.unique_id}/")
        assert resp.status_code in (200, 204)

        assert Company.objects.get(pk=company.pk).is_deleted is True
        assert Project.objects.get(pk=project.pk).is_deleted is True
        assert District.objects.get(pk=district.pk).is_deleted is True

    def test_deleting_company_cascades_through_department(
        self, auth_client, company, project
    ):
        from app.models.superadmin_masters.company import Company
        from app.models.staff_creations.department import Department

        department = Department.objects.create(
            department_name="Sanitation",
            department_code="SAN",
            company_id=company.unique_id,
            project_id=project.unique_id,
        )

        resp = auth_client.delete(f"/api/v1/superadmin/company/{company.unique_id}/")
        assert resp.status_code in (200, 204)

        assert Company.objects.get(pk=company.pk).is_deleted is True
        assert Department.objects.get(pk=department.pk).is_deleted is True

    def test_sibling_company_is_untouched(self, auth_client, company, project):
        from app.models.superadmin_masters.company import Company
        from app.models.superadmin_masters.project import Project

        sibling_company = Company.objects.create(name="Sibling Company")
        sibling_project = Project.objects.create(
            name="Sibling Project", company_id=sibling_company.unique_id
        )

        resp = auth_client.delete(f"/api/v1/superadmin/company/{company.unique_id}/")
        assert resp.status_code in (200, 204)

        assert Company.objects.get(pk=sibling_company.pk).is_deleted is False
        assert Project.objects.get(pk=sibling_project.pk).is_deleted is False


@pytest.mark.django_db
class TestProjectCascadeSoftDelete:
    def test_deleting_project_cascades_through_district_and_department(
        self, auth_client, company, project, continent, country, state
    ):
        from app.models.superadmin_masters.project import Project
        from app.models.masters.district import District
        from app.models.staff_creations.department import Department

        district = District.objects.create(
            name="Cascade District",
            continent_id=continent.unique_id,
            country_id=country.unique_id,
            state_id=state.unique_id,
            company_id=company.unique_id,
            project_id=project.unique_id,
        )
        department = Department.objects.create(
            department_name="Sanitation",
            department_code="SAN2",
            company_id=company.unique_id,
            project_id=project.unique_id,
        )

        resp = auth_client.delete(f"/api/v1/superadmin/project/{project.unique_id}/")
        assert resp.status_code in (200, 204)

        assert Project.objects.get(pk=project.pk).is_deleted is True
        assert District.objects.get(pk=district.pk).is_deleted is True
        assert Department.objects.get(pk=department.pk).is_deleted is True

    def test_sibling_project_is_untouched(self, auth_client, company, project):
        from app.models.superadmin_masters.project import Project

        sibling_project = Project.objects.create(
            name="Sibling Project", company_id=company.unique_id
        )

        resp = auth_client.delete(f"/api/v1/superadmin/project/{project.unique_id}/")
        assert resp.status_code in (200, 204)

        assert Project.objects.get(pk=sibling_project.pk).is_deleted is False
