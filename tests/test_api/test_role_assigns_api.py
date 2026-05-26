"""API tests for UserType and StaffUserType endpoints."""
import pytest
from app.models.role_assigns.userType import UserType
from app.models.role_assigns.staffUserType import StaffUserType


@pytest.mark.django_db
class TestUserTypeAPI:
    BASE = "/api/v1/role-assigns/user-type/"

    def test_list_unauthenticated(self, api_client):
        resp = api_client.get(self.BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated(self, auth_client, user_type):
        resp = auth_client.get(self.BASE)
        assert resp.status_code == 200

    def test_create(self, auth_client):
        resp = auth_client.post(self.BASE, {"name": "Manager"}, format="json")
        assert resp.status_code in (200, 201)

    def test_retrieve(self, auth_client, user_type):
        resp = auth_client.get(f"{self.BASE}{user_type.unique_id}/")
        assert resp.status_code == 200
        assert resp.json().get("name") == user_type.name

    def test_update(self, auth_client, user_type):
        resp = auth_client.patch(
            f"{self.BASE}{user_type.unique_id}/",
            {"name": "Senior Staff"},
            format="json",
        )
        assert resp.status_code in (200, 204)

    def test_delete(self, auth_client, user_type):
        resp = auth_client.delete(f"{self.BASE}{user_type.unique_id}/")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestStaffUserTypeAPI:
    BASE = "/api/v1/role-assigns/staffusertypes/"

    def test_list_authenticated(self, auth_client, user_type):
        sut = StaffUserType.objects.create(name="driver", usertype_id=user_type)
        resp = auth_client.get(self.BASE)
        assert resp.status_code == 200

    def test_create(self, auth_client, user_type):
        resp = auth_client.post(
            self.BASE,
            {"name": "company_operator", "usertype_id": user_type.pk},
            format="json",
        )
        assert resp.status_code in (200, 201)
