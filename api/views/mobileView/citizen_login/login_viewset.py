from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework import status
from rest_framework.authtoken.models import Token as AuthToken
from rest_framework.response import Response
from rest_framework.views import APIView

from api.apps.customercreation import CustomerCreation
from api.apps.userType import UserType
from api.serializers.mobileView.citizenLogin.login_serializer import LoginSerializer


class CitizenLogin(APIView):
    @staticmethod
    def _password_matches(stored_password, raw_password):
        """
        stored_password: the hashed password (or plain if your DB stores plain — not recommended)
        raw_password: the password provided by the user
        """
        if not stored_password:
            return False
        # Try using Django's check_password first (handles hashed passwords)
        try:
            return check_password(raw_password, stored_password)
        except (ValueError, TypeError):
            # Fallback to direct compare if stored_password is plain text (not recommended).
            return stored_password == raw_password

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"status": False, "message": "Invalid payload", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_type_identifier = serializer.validated_data["user_type"]
        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        # Note: use the correct field name for deletion flag (is_delete) consistently
        user_type = UserType.objects.filter(
            Q(name__iexact=user_type_identifier) | Q(unique_id__iexact=user_type_identifier),
            is_active=True,
            is_delete=False,
        ).first()

        if not user_type:
            return Response(
                {"status": False, "message": "Unknown user type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer = CustomerCreation.objects.filter(
            Q(contact_no__iexact=username) | Q(customer_name__iexact=username),
            is_active=True,
            is_deleted=False,
            user_type=user_type,
        ).first()

        if not customer:
            return Response(
                {"status": False, "message": "Customer record not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check password safely (supports hashed and plain fallback)
        # if not self._password_matches(customer.password, password):
        if(customer.password != password):
            return Response(
                {"status": False, "message": "Invalid credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, _ = User.objects.get_or_create(
            username=customer.contact_no,
            defaults={
                "first_name": customer.customer_name,
                "email": f"{customer.contact_no}@example.com",
            },
        )
        user.is_active = True
        user.save(update_fields=["is_active"])

        token, _ = AuthToken.objects.get_or_create(user=user)
        return Response(
            {
                "status": True,
                "message": "Login successful",
                "token": token.key,
                "user": {
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
            },
            status=status.HTTP_200_OK,
        )