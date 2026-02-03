# api/views/desktopView/users/login_viewset.py

from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import AccessToken

from api.apps.loginAudit import LoginAudit
from api.serializers.desktopView.users.login_serializer import LoginSerializer


class LoginViewSet(ViewSet):
    permission_classes = [AllowAny]

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
        user_type = serializer.validated_data.get("user_type", "staff")
        staffusertype_id = serializer.validated_data.get("staffusertype_id")

        # -------------------------
        # ROLE RESOLUTION
        # -------------------------
        email = None
        emp_id = None
        employee_id = None
        name = None
        role = None

        if user_type == "customer":
            name = user.customer_name
            role = "customer"
            email = getattr(user, "email", None)
        else:
            # Staff login
            name = user.employee_name
            if user.staffusertype_id:
                role = user.staffusertype_id.name
            else:
                role = "staff"
            if hasattr(user, "personal_details"):
                email = user.personal_details.contact_email
            emp_id = getattr(user, "staff_unique_id", None)
            employee_id = getattr(user, "emp_id", None)
            if not employee_id and getattr(user, "id", None) is not None:
                employee_id = f"{user.id:08d}"

        # -------------------------
        # JWT CREATION
        # -------------------------
        access = AccessToken.for_user(user)

        # Get the correct unique identifier based on user type
        if user_type == "customer":
            user_unique_id = user.unique_id
        else:
            user_unique_id = user.staff_unique_id

        access["unique_id"] = user_unique_id
        access["user_type"] = user_type
        access["name"] = name
        access["role"] = role
        access["email"] = email
        access["permissions"] = permissions
        access["emp_id"] = emp_id
        access["employee_id"] = employee_id
        access["company_unique_id"] = getattr(getattr(user, "company_id", None), "unique_id", None)
        access["project_unique_id"] = getattr(getattr(user, "project_id", None), "unique_id", None)

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
            user_unique_id=user_unique_id,
            username=login_identifier,  
            password=login_password,
            ip_address=getattr(request, "ip_address", ""),
            user_agent=getattr(request, "user_agent", ""),
            success=True,
            reason=None
        )

        return Response(
            {
                "unique_id": user_unique_id,
                "user_type": user_type,
                "name": name,
                "role": role,
                "permissions": permissions,
                "access_token": token,
                "email": email,
                "emp_id": emp_id,
                "employee_id": employee_id,
            },
            status=status.HTTP_200_OK
        )
