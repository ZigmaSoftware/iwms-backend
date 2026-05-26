"""API tests for UserType endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/role-assigns/user-type/"


@pytest.mark.django_db
class TestUserTypeAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client, user_type):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestUserTypeAPICreate:
    def test_create_returns_success(self, auth_client):
        resp = auth_client.post(BASE, {"name": "Manager"}, format="json")
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestUserTypeAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, user_type):
        resp = auth_client.get(f"{BASE}{user_type.unique_id}/")
        assert resp.status_code == 200

    def test_retrieve_returns_correct_name(self, auth_client, user_type):
        resp = auth_client.get(f"{BASE}{user_type.unique_id}/")
        assert resp.json().get("name") == user_type.name


@pytest.mark.django_db
class TestUserTypeAPIUpdate:
    def test_patch_returns_success(self, auth_client, user_type):
        resp = auth_client.patch(f"{BASE}{user_type.unique_id}/", {"name": "Senior Staff"}, format="json")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestUserTypeAPIDelete:
    def test_delete_returns_success(self, auth_client, user_type):
        resp = auth_client.delete(f"{BASE}{user_type.unique_id}/")
        assert resp.status_code in (200, 204)
