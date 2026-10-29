import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.leader_management.panchayat_leader_login import PanchayatLeaderLogin
from app.models.masters.leader_management.district_leader_login import DistrictLeaderLogin
from app.services.login_session import validate_session
from app.authentication.cookies import bearer_token, request_token


class JWTUserAuthentication(BaseAuthentication):
    """
    Resolve a user from the Bearer token or the web portal's auth cookie.
    Supports both Staff (Staffcreation) and Customer (CustomerCreation) authentication.
    """

    def authenticate_header(self, request):
        """Tell DRF that authentication failures use the Bearer challenge.

        Without this header DRF converts ``NotAuthenticated`` and
        ``AuthenticationFailed`` responses to HTTP 403, which makes an expired
        or invalid JWT look like an authorization failure to the frontend.
        """
        return "Bearer"

    def authenticate(self, request):
        raw_request = getattr(request, "_request", None)
        existing_user = getattr(raw_request, "user", None)
        
        # Check if already authenticated via other means
        if hasattr(existing_user, 'staff_unique_id'):
            return (existing_user, None)
        if hasattr(existing_user, 'unique_id') and hasattr(existing_user, 'customer_name'):
            return (existing_user, None)

        token = bearer_token(request)
        if token:
            return self._authenticate_token(request, token)

        # Web portal's HttpOnly cookie. A stale one (expired, logged out)
        # just means "not signed in": raising here would also fail public
        # endpoints like login, which DRF authenticates eagerly.
        token = request_token(request)
        if not token:
            return None
        try:
            return self._authenticate_token(request, token)
        except AuthenticationFailed:
            return None

    def _authenticate_token(self, request, token):
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationFailed("Token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationFailed("Invalid token") from exc

        session_error = validate_session(payload)
        if session_error:
            raise AuthenticationFailed(session_error, code="session_ended")

        unique_id = payload.get("unique_id")
        if not unique_id:
            raise AuthenticationFailed("Invalid token")

        # Try to find user in Staffcreation first (uses staff_unique_id)
        staff = Staffcreation.objects.filter(staff_unique_id=unique_id).first()
        if staff:
            if not staff.login_enabled:
                raise AuthenticationFailed("Login is disabled for this user")
            request.jwt_payload = payload
            return (staff, None)
        
        # Try to find user in CustomerCreation (uses unique_id)
        customer = CustomerCreation.objects.filter(unique_id=unique_id).first()
        if customer:
            request.jwt_payload = payload
            return (customer, None)

        # Try to find user in PanchayatLeaderLogin (uses unique_id with prefix PLDR-)
        leader = PanchayatLeaderLogin.objects.filter(unique_id=unique_id).first()
        if leader:
            request.jwt_payload = payload
            return (leader, None)

        # Try to find user in DistrictLeaderLogin (uses unique_id with prefix DLDR-)
        district_leader = DistrictLeaderLogin.objects.filter(unique_id=unique_id).first()
        if district_leader:
            request.jwt_payload = payload
            return (district_leader, None)

        # Fall back to Django User (platform super admin)
        UserModel = get_user_model()
        user = UserModel.objects.filter(unique_id=unique_id).first()
        if not user:
            user_id = payload.get("user_id")
            if user_id:
                user = UserModel.objects.filter(pk=user_id).first()
        if user:
            request.jwt_payload = payload
            return (user, None)

        raise AuthenticationFailed("User not found")
