"""API tests for ProjectStaffHierarchy endpoint."""
import pytest

from app.models.superadmin.role_management.projectStaffHierarchy import ProjectStaffHierarchy
from app.models.superadmin.role_management.staffUserType import StaffUserType


BASE = "/api/v1/role-assigns/project-staff-hierarchy/"


@pytest.fixture
def staff_roles(db, user_type):
    driver = StaffUserType.objects.create(
        name="company_driver",
        usertype_id=user_type.unique_id,
    )
    supervisor = StaffUserType.objects.create(
        name="company_supervisor",
        usertype_id=user_type.unique_id,
    )
    return driver, supervisor


@pytest.mark.django_db
class TestProjectStaffHierarchyAPIList:
    def test_list_returns_200_and_resolved_names(self, auth_client, project, staff_roles):
        driver, supervisor = staff_roles
        hierarchy = ProjectStaffHierarchy.objects.create(
            project_id=project.unique_id,
            staffusertype_id=driver.unique_id,
            reports_to_staffusertype_id=supervisor.unique_id,
            level=1,
        )

        resp = auth_client.get(BASE)

        assert resp.status_code == 200
        row = next(item for item in resp.data if item["unique_id"] == hierarchy.unique_id)
        assert row["project_id"] == project.unique_id
        assert row["project_name"] == project.name
        assert row["staffusertype_id"] == driver.unique_id
        assert row["staffusertype_name"] == driver.name
        assert row["reports_to_staffusertype_id"] == supervisor.unique_id
        assert row["reports_to_staffusertype_name"] == supervisor.name


@pytest.mark.django_db
class TestProjectStaffHierarchyAPICreate:
    def test_create_returns_success(self, auth_client, project, staff_roles):
        driver, supervisor = staff_roles

        resp = auth_client.post(
            BASE,
            {
                "project_id": project.unique_id,
                "staffusertype_id": driver.unique_id,
                "reports_to_staffusertype_id": supervisor.unique_id,
                "level": 1,
            },
            format="json",
        )

        assert resp.status_code in (200, 201)
        assert resp.data["project_id"] == project.unique_id
        assert resp.data["staffusertype_id"] == driver.unique_id
        assert resp.data["reports_to_staffusertype_id"] == supervisor.unique_id
