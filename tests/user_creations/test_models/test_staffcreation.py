"""Unit tests for StaffcreationOfficeDetails model — CRUD + constraints."""
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
class TestStaffCreationCreate:
    def test_basic_create(self, staff):
        assert staff.employee_name == "John Driver"

    def test_unique_id_prefix(self, staff):
        assert staff.staff_unique_id.startswith("STC-")

    def test_staff_id_starts_at_one(self, staff):
        assert staff.staff_id == "STF0001"

    def test_staff_id_is_exposed_by_serializer(self, staff):
        from app.serializers.superadmin.staff_management.staffcreation_serializer import (
            StaffcreationSerializer,
        )

        assert StaffcreationSerializer(staff).data["staff_id"] == "STF0001"

    def test_str_contains_name(self, staff):
        assert "John Driver" in str(staff)

    def test_emp_id_auto_generated(self, staff):
        assert staff.emp_id is not None
        assert len(staff.emp_id) > 0

    def test_foreign_key_company(self, staff, company):
        assert staff.company_id == company

    def test_unique_ids_differ(self, staff, company, project):
        s2 = StaffcreationOfficeDetails.objects.create(
            employee_name="Jane Operator",
            company_id=company,
            project_id=project,
        )
        assert staff.staff_unique_id != s2.staff_unique_id
        assert s2.staff_id == "STF0002"

    def test_staff_id_restarts_for_another_project(self, staff, company):
        from app.models.superadmin_masters.project import Project

        other_project = Project.objects.create(name="Other Project", company_id=company)
        s2 = StaffcreationOfficeDetails.objects.create(
            employee_name="Other Project Driver",
            company_id=company,
            project_id=other_project,
        )
        assert s2.staff_id == "STF0001"


@pytest.mark.django_db
class TestStaffCreationDefaults:
    def test_is_active_default_true(self, staff):
        assert staff.is_active is True

    def test_is_deleted_default_false(self, staff):
        assert staff.is_deleted is False

    def test_optional_fields_nullable(self, staff):
        assert staff.department is None
        assert staff.designation is None
        assert staff.office_email is None


@pytest.mark.django_db
class TestStaffCreationSoftDelete:
    def test_soft_delete(self, staff):
        staff.delete()
        staff.refresh_from_db()
        assert staff.is_deleted is True
        assert staff.is_active is False


@pytest.mark.django_db
class TestStaffCreationUpdate:
    def test_update_employee_name(self, staff):
        staff.employee_name = "Updated Name"
        staff.save()
        staff.refresh_from_db()
        assert staff.employee_name == "Updated Name"

    def test_update_repairs_missing_staff_id(self, staff):
        StaffcreationOfficeDetails.objects.filter(pk=staff.pk).update(staff_id="")
        staff.refresh_from_db()
        staff.employee_name = "Repaired Staff"
        staff.save(update_fields=["employee_name"])
        staff.refresh_from_db()

        assert staff.staff_id == "STF0001"
