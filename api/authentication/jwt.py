import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from api.apps.userCreation import User


class JWTUserAuthentication(BaseAuthentication):
    """
    Resolve a user from the Bearer token used by ModulePermissionMiddleware.
    """

    def authenticate(self, request):
        raw_request = getattr(request, "_request", None)
        existing_user = getattr(raw_request, "user", None)
        if getattr(existing_user, "unique_id", None):
            return (existing_user, None)

        auth = request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer "):
            return None

        token = auth.split(" ", 1)[1].strip()
        if not token:
            return None

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationFailed("Token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationFailed("Invalid token") from exc

        unique_id = payload.get("unique_id")
        if not unique_id:
            raise AuthenticationFailed("Invalid token")

        user = User.objects.filter(unique_id=unique_id).first()
        if not user:
            raise AuthenticationFailed("User not found")

        request.jwt_payload = payload
        return (user, None)
