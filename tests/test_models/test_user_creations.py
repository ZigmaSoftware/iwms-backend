"""Model tests for StaffcreationOfficeDetails."""
import pytest
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails


@pytest.fixture
def staff(db, company, project):
    return StaffcreationOfficeDetails.objects.create(
        employee_name="John Driver",
        company_id=company,
        project_id=project,
    )


@pytest.mark.django_db
class TestStaffcreationOfficeDetailsModel:

    def test_create(self, staff):
        assert staff.employee_name == "John Driver"
        assert staff.staff_unique_id.startswith("STC-")

    def test_str(self, staff):
        assert "John Driver" in str(staff)

    def test_default_flags(self, staff):
        assert staff.is_active is True
        assert staff.is_deleted is False

    def test_emp_id_auto_generated(self, staff):
        assert staff.emp_id is not None
        assert len(staff.emp_id) > 0

    def test_soft_delete(self, staff):
        staff.delete()
        staff.refresh_from_db()
        assert staff.is_deleted is True
        assert staff.is_active is False

    def test_optional_fields_nullable(self, staff):
        assert staff.department is None
        assert staff.designation is None
        assert staff.office_email is None

    def test_foreign_key_company(self, staff, company):
        assert staff.company_id == company

    def test_unique_ids_differ(self, staff, company, project):
        s2 = StaffcreationOfficeDetails.objects.create(
            employee_name="Jane Operator",
            company_id=company,
            project_id=project,
        )
        assert staff.staff_unique_id != s2.staff_unique_id
