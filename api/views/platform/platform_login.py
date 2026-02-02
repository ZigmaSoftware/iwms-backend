from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

from api.serializers.platform.platform_login_serializer import PlatformLoginSerializer


class PlatformLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PlatformLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"].strip()
        password = serializer.validated_data["password"].strip()

        user = authenticate(request=request, username=username, password=password)
        if not user:
            raise AuthenticationFailed("Invalid username or password")

        if not getattr(user, "is_superuser", False) or getattr(user, "company_id", None) is not None:
            raise PermissionDenied("Not a platform super admin")

        access = AccessToken.for_user(user)
        access["unique_id"] = getattr(user, "unique_id", None)
        access["username"] = getattr(user, "username", None)
        access["platform"] = True

        return Response(
            {
                "access_token": str(access),
                "unique_id": getattr(user, "unique_id", None),
                "username": getattr(user, "username", None),
            },
            status=status.HTTP_200_OK,
        )
