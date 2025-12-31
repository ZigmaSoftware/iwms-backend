# api/views/desktopView/users/login_viewset.py

from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken

from api.apps.loginAudit import LoginAudit
from api.serializers.desktopView.users.login_serializer import LoginSerializer


class LoginViewSet(ViewSet):

    def create(self, request):
        login_identifier = request.data.get("username", "").strip()
        login_password = request.data.get("password", "").strip()

        serializer = LoginSerializer(data=request.data)

        # -------------------------
        # LOGIN FAILURE AUDIT
        # -------------------------
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            LoginAudit.objects.create(
                user_unique_id=None,
                username=login_identifier,
                password=login_password,
                ip_address=getattr(request, "ip_address", ""),
                user_agent=getattr(request, "user_agent", ""),
                success=False,
                reason="Invalid credentials"
            )
            raise

        user = serializer.validated_data["user"]
        permissions = serializer.validated_data["permissions"]

        # -------------------------
        # ROLE RESOLUTION
        # -------------------------
        email = None

        if user.user_type_id.name.lower() == "customer":
            name = user.customer_id.customer_name
            role = "customer"
            email = getattr(user.customer_id, "email", None)
        else:
            name = user.staff_id.employee_name
            role = user.staffusertype_id.name
            if hasattr(user.staff_id, "personal_details"):
                email = user.staff_id.personal_details.contact_email

        # -------------------------
        # JWT CREATION
        # -------------------------
        access = AccessToken.for_user(user)

        access["unique_id"] = user.unique_id
        access["user_type"] = user.user_type_id.name
        access["name"] = name
        access["role"] = role
        access["email"] = email
        access["permissions"] = permissions

        iat = access["iat"]
        exp = access["exp"]

        access["valid_seconds"] = exp - iat
        access["valid_hours"] = round((exp - iat) / 3600, 2)
        access["valid_days"] = round((exp - iat) / 86400, 4)

        token = str(access)

        # -------------------------
        # LOGIN SUCCESS AUDIT 
        # -------------------------
        LoginAudit.objects.create(
            user_unique_id=user.unique_id,
            username=login_identifier,  
            password=login_password,
            ip_address=getattr(request, "ip_address", ""),
            user_agent=getattr(request, "user_agent", ""),
            success=True,
            reason=None
        )

        return Response(
            {
                "unique_id": user.unique_id,
                "user_type": user.user_type_id.name,
                "name": name,
                "role": role,
                "permissions": permissions,
                "access_token": token,
                "email": email,
            },
            status=status.HTTP_200_OK
        )
