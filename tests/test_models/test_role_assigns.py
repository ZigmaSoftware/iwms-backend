"""Unit tests for UserType, StaffUserType models."""
import pytest
from app.models.role_assigns.userType import UserType
from app.models.role_assigns.staffUserType import StaffUserType


@pytest.mark.django_db
class TestUserTypeModel:
    def test_create(self):
        u = UserType.objects.create(name="Customer")
        assert u.name == "Customer"
        assert u.unique_id.startswith("UTYPE-")

    def test_str(self):
        u = UserType.objects.create(name="Admin")
        assert str(u) == "Admin"

    def test_default_flags(self):
        u = UserType.objects.create(name="Staff")
        assert u.is_active is True
        assert u.is_deleted is False

    def test_soft_delete(self):
        u = UserType.objects.create(name="Temp")
        u.delete()
        u.refresh_from_db()
        assert u.is_active is False
        assert u.is_deleted is True

    def test_name_unique(self):
        from django.db import IntegrityError
        UserType.objects.create(name="Unique")
        with pytest.raises(IntegrityError):
            UserType.objects.create(name="Unique")

    def test_ordering_alphabetical(self):
        UserType.objects.create(name="Zebra")
        UserType.objects.create(name="Apple")
        names = list(UserType.objects.values_list("name", flat=True))
        assert names == sorted(names)


@pytest.mark.django_db
class TestStaffUserTypeModel:
    def test_create(self, user_type):
        s = StaffUserType.objects.create(name="driver", usertype_id=user_type)
        assert s.name == "driver"
        assert s.unique_id.startswith("STUSRTYPE-")

    def test_str(self, user_type):
        s = StaffUserType.objects.create(name="operator", usertype_id=user_type)
        assert "operator" in str(s)

    def test_default_flags(self, user_type):
        s = StaffUserType.objects.create(name="supervisor", usertype_id=user_type)
        assert s.is_active is True
        assert s.is_deleted is False

    def test_soft_delete(self, user_type):
        s = StaffUserType.objects.create(name="helper", usertype_id=user_type)
        s.delete()
        s.refresh_from_db()
        assert s.is_active is False
        assert s.is_deleted is True

    def test_foreign_key_usertype(self, user_type):
        s = StaffUserType.objects.create(name="checker", usertype_id=user_type)
        assert s.usertype_id == user_type
