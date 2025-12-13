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

        access = AccessToken.for_user(user)
        token = str(access)

        email = None  # default

        # Identify role
        if user.user_type.name.lower() == "customer":
            name = user.customer_id.customer_name
            role = "customer"
            email = getattr(user.customer_id, "email", None)

        else:
            name = user.staff_id.employee_name
            role = user.staffusertype_id.name

            # SAFE EMAIL ACCESS
            if hasattr(user.staff_id, "personal_details") and user.staff_id.personal_details:
                email = user.staff_id.personal_details.contact_email

        return Response({
            "unique_id": user.unique_id,
            "user_type": user.user_type.name,
            "name": name,
            "role": role,
            "permissions": permissions,
            "access_token": token,
            "email": email
        }, status=status.HTTP_200_OK)
