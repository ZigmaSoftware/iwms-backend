from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken

from ....serializers.mobileView.citizenLogin.newlogin_serializer import LoginSerializer


class LoginViewSet(ViewSet):
    queryset = []

    def create(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        permissions = serializer.validated_data.get("permissions", {})

        # Identify role and email
        email = None
        emp_id = None
        
        if user.user_type_id.name.lower() == "customer":
            name = user.customer_id.customer_name
            role = "customer"
            email = getattr(user.customer_id, "email", None)
        else:
            name = user.staff_id.employee_name
            role = user.staffusertype_id.name
            if hasattr(user.staff_id, "personal_details"):
                email = user.staff_id.personal_details.contact_email
            emp_id = getattr(user.staff_id, "staff_unique_id", None)

        # Generate access token with all required fields
        access = AccessToken.for_user(user)
        
        # Add custom claims to match desktop login
        access["unique_id"] = user.unique_id
        access["user_type"] = user.user_type_id.name
        access["name"] = name
        access["role"] = role
        access["email"] = email
        access["permissions"] = permissions
        access["emp_id"] = emp_id
        
        iat = access["iat"]
        exp = access["exp"]
        
        access["valid_seconds"] = exp - iat
        access["valid_hours"] = round((exp - iat) / 3600, 2)
        access["valid_days"] = round((exp - iat) / 86400, 4)
        
        token = str(access)

        return Response({
            "unique_id": user.unique_id,
            "user_type": user.user_type_id.name,
            "name": name,
            "role": role,
            "permissions": permissions,
            "access_token": token,
            "email": email,
            "emp_id": emp_id,
            'customer_id': user.customer_id_id if user.customer_id else None
        }, status=status.HTTP_200_OK)
