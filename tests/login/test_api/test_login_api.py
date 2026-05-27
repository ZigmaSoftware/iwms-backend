"""API tests for Login and MyPermissions endpoints."""
import pytest

LOGIN_BASE = "/api/v1/login/login-user/"
PERMISSIONS_BASE = "/api/v1/login/my-permissions/"


@pytest.mark.django_db
class TestLoginAPI:
    def test_login_with_invalid_credentials_returns_400(self, api_client):
        resp = api_client.post(
            LOGIN_BASE,
            {"username": "nonexistent_user", "password": "wrongpassword"},
            format="json",
        )
        assert resp.status_code in (400, 401)

    def test_login_endpoint_is_publicly_accessible(self, api_client):
        resp = api_client.post(LOGIN_BASE, {}, format="json")
        assert resp.status_code != 405  # endpoint exists (not method-not-allowed)


@pytest.mark.django_db
class TestMyPermissionsAPI:
    def test_permissions_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(PERMISSIONS_BASE)
        assert resp.status_code in (401, 403)

    def test_permissions_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(PERMISSIONS_BASE)
        assert resp.status_code == 200
