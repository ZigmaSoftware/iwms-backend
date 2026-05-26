"""Unit tests for Company, Project, and User models."""
import pytest
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.superadmin_masters.auth_user import User


@pytest.mark.django_db
class TestCompanyModel:
    def test_create(self):
        c = Company.objects.create(name="ACME Corp")
        assert c.name == "ACME Corp"
        assert c.unique_id.startswith("CMP-")

    def test_str(self):
        c = Company.objects.create(name="Beta Ltd")
        assert str(c) == "Beta Ltd"

    def test_default_flags(self):
        c = Company.objects.create(name="Gamma Inc")
        assert c.is_active is True
        assert c.is_deleted is False

    def test_soft_delete(self):
        c = Company.objects.create(name="Delete Me")
        c.delete()
        c.refresh_from_db()
        assert c.is_deleted is True
        assert c.is_active is False

    def test_description_optional(self):
        c = Company.objects.create(name="Silent Corp")
        assert c.description is None

    def test_unique_ids_differ(self):
        c1 = Company.objects.create(name="Co1")
        c2 = Company.objects.create(name="Co2")
        assert c1.unique_id != c2.unique_id

    def test_ordering_alphabetical(self):
        Company.objects.create(name="Zebra")
        Company.objects.create(name="Apple")
        names = list(Company.objects.values_list("name", flat=True))
        assert names == sorted(names)


@pytest.mark.django_db
class TestProjectModel:
    def test_create(self, company):
        p = Project.objects.create(name="Main Project", company_id=company)
        assert p.name == "Main Project"
        assert p.unique_id.startswith("PROJ-")

    def test_str(self, company):
        p = Project.objects.create(name="My Project", company_id=company)
        assert "My Project" in str(p)

    def test_default_flags(self, project):
        assert project.is_active is True
        assert project.is_deleted is False

    def test_soft_delete(self, project):
        project.delete()
        project.refresh_from_db()
        assert project.is_deleted is True

    def test_foreign_key_company(self, project, company):
        assert project.company_id == company


@pytest.mark.django_db
class TestUserModel:
    def test_create_superuser(self):
        u = User.objects.create_superuser(
            username="testadmin",
            password="pass1234",
        )
        assert u.is_superuser is True
        assert u.username == "testadmin"
        assert u.unique_id.startswith("SUPUSER-")

    def test_superuser_has_no_company(self):
        u = User.objects.create_superuser(
            username="pureplatform",
            password="pass1234",
        )
        assert u.company_id is None
        assert u.project_id is None

    def test_password_is_hashed(self):
        u = User.objects.create_superuser(
            username="hashtest",
            password="plaintext",
        )
        assert u.password != "plaintext"
        assert u.check_password("plaintext") is True

    def test_str_returns_username(self):
        u = User.objects.create_superuser(
            username="displayuser",
            password="pass",
        )
        assert str(u) == "displayuser"

    def test_default_flags(self):
        u = User.objects.create_superuser(
            username="flagtest",
            password="pass",
        )
        assert u.is_active is True
        assert u.is_deleted is False

    def test_non_superuser_requires_company(self):
        with pytest.raises(ValueError, match="must belong to a company"):
            User.objects.create_user(username="nocompany", password="pass")
