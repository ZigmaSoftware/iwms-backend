# api/views/desktopView/users/login_viewset.py

from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import AccessToken

from app.models.user_creations.loginAudit import LoginAudit
from app.serializers.login.login_serializer import LoginSerializer


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
        profile_object = serializer.validated_data.get("profile_object")
        company_unique_id = serializer.validated_data.get("company_unique_id")
        staffusertype_unique_id = serializer.validated_data.get("staffusertype_id")

        # -------------------------
        # ROLE RESOLUTION
        # -------------------------
        email = None
        emp_id = None
        employee_id = None
        name = None
        role = None

        if user_type == "customer":
            target = profile_object or user
            name = getattr(target, "customer_name", None) or getattr(user, "customer_name", None)
            role = "customer"
            email = getattr(target, "email", None) or getattr(user, "email", None)
        elif user_type == "platform":
            name = (
                getattr(profile_object, "employee_name", None)
                or getattr(profile_object, "username", None)
                or getattr(user, "employee_name", None)
                or getattr(user, "username", None)
                or getattr(user, "email", None)
                or "platform"
            )
            role = "superadmin" if getattr(user, "is_superuser", False) else "platform"
            email = getattr(user, "email", None)
        else:
            # Staff login
            target = profile_object or user
            name = getattr(target, "employee_name", None) or getattr(user, "username", None)
            staff_role = getattr(target, "staffusertype_id", None) or getattr(user, "staffusertype_id", None)
            if staff_role:
                role = staff_role.name
            else:
                role = "staff"
            if hasattr(target, "personal_details") and getattr(target, "personal_details"):
                email = target.personal_details.contact_email
            emp_id = getattr(target, "staff_unique_id", None)
            employee_id = getattr(target, "emp_id", None) or getattr(user, "emp_id", None)
            if not employee_id and getattr(user, "id", None) is not None:
                employee_id = f"{user.id:08d}"

        # -------------------------
        # JWT CREATION
        # -------------------------
        # Get the correct unique identifier based on user type
        user_unique_id = getattr(user, "unique_id", None) or getattr(user, "staff_unique_id", None)
        if not user_unique_id and getattr(user, "id", None) is not None:
            user_unique_id = str(user.id)

        company = None
        if profile_object:
            company = getattr(profile_object, "company_id", None)
        if not company:
            company = getattr(user, "company_id", None)

        if company:
            company_name = getattr(company, "name", None)
            company_unique_id = company_unique_id or getattr(company, "unique_id", None)
        else:
            company_name = None

        profile_payload = {
            "user_type": user_type,
            "unique_id": user_unique_id,
            "name": name,
            "role": role,
            "email": email,
            "company_unique_id": company_unique_id,
            "company_name": company_name,
        }

        if user_type == "staff":
            staff_source = profile_object or user
            profile_payload.update(
                {
                    "staff_unique_id": emp_id,
                    "employee_id": employee_id,
                    "employee_name": getattr(staff_source, "employee_name", None) or name,
                    "emp_id": emp_id,
                    "staffusertype_unique_id": staffusertype_unique_id,
                }
            )
        elif user_type == "customer":
            customer_source = profile_object or user
            profile_payload.update(
                {
                    "customer_unique_id": getattr(customer_source, "unique_id", None),
                    "customer_name": getattr(customer_source, "customer_name", None) or name,
                    "contact_no": getattr(customer_source, "contact_no", None),
                }
            )
        else:
            profile_payload.update(
                {
                    "platform_username": getattr(user, "username", None),
                    "is_superuser": getattr(user, "is_superuser", False),
                }
            )

        access = AccessToken.for_user(user)

        access["unique_id"] = user_unique_id
        access["user_type"] = user_type
        access["name"] = name
        access["role"] = role
        access["email"] = email
        access["permissions"] = permissions
        access["emp_id"] = emp_id
        access["employee_id"] = employee_id
        access["company_unique_id"] = company_unique_id
        access["company_name"] = company_name
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
                "token_type": "Bearer",
                "expires_in": exp - iat,
                "email": email,
                "emp_id": emp_id,
                "employee_id": employee_id,
                "company_unique_id": company_unique_id,
                "company_name": company_name,
                "profile": profile_payload,
            },
            status=status.HTTP_200_OK
        )
