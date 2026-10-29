"""
Web portals authenticate with an HttpOnly cookie instead of a Bearer token.
"""
import pytest
from django.core.cache import cache

from app.authentication.cookies import PORTAL_COOKIES

LOGIN_URL = "/api/v1/login/login-user/"
LOGOUT_URL = "/api/v1/login/logout/"
ME_URL = "/api/v1/login/me/"
PROTECTED_URL = "/api/v1/audits/login-audit/"

ADMIN_COOKIE = PORTAL_COOKIES["admin"]


def _portal(name="admin"):
    return {"HTTP_X_IWMS_PORTAL": name}


def _web_login(api_client, portal="admin"):
    from app.models.superadmin_masters.auth_user import User
    User.objects.create_superuser(
        username="cookie_admin", password="Cookie@123", unique_id="U-COOKIE-01",
    )
    return api_client.post(
        LOGIN_URL,
        {"username": "cookie_admin", "password": "Cookie@123", "client": "web"},
        format="json",
        **_portal(portal),
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestLoginCookie:
    def test_web_login_sets_httponly_cookie_and_hides_token(self, api_client):
        resp = _web_login(api_client)
        assert resp.status_code == 200
        assert "access_token" not in resp.data
        cookie = resp.cookies[ADMIN_COOKIE]
        assert cookie.value
        assert cookie["httponly"]
        assert cookie["samesite"] == "Lax"

    def test_login_without_portal_header_still_returns_token(self, api_client):
        from app.models.superadmin_masters.auth_user import User
        User.objects.create_superuser(
            username="mobile_admin", password="Mobile@123", unique_id="U-COOKIE-02",
        )
        resp = api_client.post(
            LOGIN_URL, {"username": "mobile_admin", "password": "Mobile@123"}, format="json",
        )
        assert resp.data["access_token"]
        assert ADMIN_COOKIE not in resp.cookies

    def test_cookie_authenticates_with_portal_header(self, api_client):
        _web_login(api_client)
        assert api_client.get(PROTECTED_URL, **_portal()).status_code == 200

    def test_cookie_ignored_without_portal_header(self, api_client):
        # The header is the CSRF guard: a bare cross-site request carries the
        # cookie but cannot add a custom header.
        _web_login(api_client)
        assert api_client.get(PROTECTED_URL).status_code == 401

    def test_other_portal_cookie_is_not_used(self, api_client):
        _web_login(api_client, portal="district")
        assert api_client.get(PROTECTED_URL, **_portal("admin")).status_code == 401

    def test_me_restores_session(self, api_client, settings):
        login = _web_login(api_client).data
        resp = api_client.get(ME_URL, **_portal())
        assert resp.status_code == 200
        assert resp.data["unique_id"] == login["unique_id"]
        assert resp.data["role"] == login["role"]
        assert resp.data["login_audit_id"] == login["login_audit_id"]
        assert resp.data["idle_timeout_seconds"] == settings.LOGIN_IDLE_TIMEOUT_SECONDS
        assert "access_token" not in resp.data

    def test_me_without_session_is_401(self, api_client):
        assert api_client.get(ME_URL, **_portal()).status_code == 401

    def test_logout_clears_cookie_and_ends_session(self, api_client):
        _web_login(api_client)
        resp = api_client.post(LOGOUT_URL, {"reason": "manual"}, format="json", **_portal())
        assert resp.status_code == 200
        assert resp.cookies[ADMIN_COOKIE].value == ""
        assert api_client.get(ME_URL, **_portal()).status_code == 401

    def test_login_works_with_stale_cookie(self, api_client):
        # An expired / logged-out cookie must not block signing in again.
        api_client.cookies[ADMIN_COOKIE] = "not-a-valid-token"
        assert _web_login(api_client).status_code == 200
