from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken

from ....serializers.desktopView.users.login_serializer import LoginSerializer

class LoginViewSet(ViewSet):
    queryset = []

    def create(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        permissions = serializer.validated_data["permissions"]

        email = None

        # -------------------------
        # ROLE RESOLUTION
        # -------------------------
        if user.user_type.name.lower() == "customer":
            name = user.customer_id.customer_name
            role = "customer"
            email = getattr(user.customer_id, "email", None)
        else:
            name = user.staff_id.employee_name
            role = user.staffusertype_id.name

            if hasattr(user.staff_id, "personal_details") and user.staff_id.personal_details:
                email = user.staff_id.personal_details.contact_email

        # -------------------------
        # JWT WITH CUSTOM CLAIMS
        # -------------------------
        access = AccessToken.for_user(user)

        access["unique_id"] = user.unique_id
        access["user_type"] = user.user_type.name
        access["name"] = name
        access["role"] = role
        access["email"] = email
        access["permissions"] = permissions
        
        # -------------------------
        # DAY CALCULATION (INSIDE TOKEN)
        # -------------------------
        iat = access["iat"]
        exp = access["exp"]
        
        valid_seconds = exp - iat
        valid_hours = round(valid_seconds / 3600, 2)
        valid_days = round(valid_seconds / 86400, 4)

        access["valid_seconds"] = valid_seconds
        access["valid_hours"] = valid_hours
        access["valid_days"] = valid_days

        token = str(access)

        # -------------------------
        # RESPONSE (EXPLICIT FIELDS)
        # -------------------------
        return Response(
            {
                "unique_id": user.unique_id,
                "user_type": user.user_type.name,
                "name": name,
                "role": role,
                "permissions": permissions,
                "access_token": token,
                "email": email,
            },
            status=status.HTTP_200_OK
        )
