# api/views/desktopView/users/login_viewset.py

from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action as drf_action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import AccessToken
from django.utils import timezone

from app.models.staff_creations.loginAudit import LoginAudit
from app.models.staff_creations.staffcreation import Staffcreation
from app.models.customers.customercreation import CustomerCreation
from app.models.customers.customer_access_configuration import CustomerAccessConfiguration
from app.serializers.login.login_serializer import LoginSerializer
from app.utils.permission_response import resolve_permission_payload
from app.utils.captcha import verify_captcha
from app.utils.request_client import is_mobile_client


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class LoginViewSet(ViewSet):
    permission_classes = [AllowAny]

    def create(self, request):
        login_identifier = request.data.get("username", "").strip()
        login_password = request.data.get("password", "").strip()
        ip_address = getattr(request, "ip_address", None) or _client_ip(request)

        # The captcha challenge is a browser defence (bot-driven credential
        # stuffing against the visible web login form) and the mobile app has
        # no captcha UI to answer it with — every mobile sign-in was failing
        # closed with "Invalid or expired captcha" the moment the web team
        # turned this on, for every user, unconditionally. Skip it for the
        # same `client: "mobile"` flag the App Module gate already relies on
        # (see LoginSerializer._enforce_app_module_gate); a browser session
        # sends no client and is unaffected.
        if not is_mobile_client(request.data):
            captcha_id = request.data.get("captcha_id", "")
            captcha_value = request.data.get("captcha_value", "")

            if not verify_captcha(captcha_id, captcha_value):
                LoginAudit.objects.create(
                    user_unique_id=None,
                    username=login_identifier,
                    password=login_password,
                    ip_address=ip_address or "",
                    user_agent=getattr(request, "user_agent", ""),
                    success=False,
                    reason="Invalid or expired captcha"
                )
                return Response(
                    {"captcha": ["Invalid or expired captcha"], "detail": "Invalid or expired captcha"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

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
                ip_address=ip_address or "",
                user_agent=getattr(request, "user_agent", ""),
                success=False,
                reason="Invalid credentials"
            )
            raise

        user = serializer.validated_data["user"]
        permissions = serializer.validated_data["permissions"]
        app_surfaces = serializer.validated_data.get("app_surfaces", [])
        app_modules = serializer.validated_data.get("app_modules", [])
        app_screens = serializer.validated_data.get("app_screens", {})
        landing = serializer.validated_data.get("landing")
        permission_version = serializer.validated_data.get("permission_version")
        generated_at = serializer.validated_data.get("generated_at")
        user_type = serializer.validated_data.get("user_type", "staff")
        profile_object = serializer.validated_data.get("profile_object")
        company_unique_id = serializer.validated_data.get("company_unique_id")
        password_expired = serializer.validated_data.get("password_expired", False)
        staffusertype_unique_id = serializer.validated_data.get("staffusertype_id")
        contractorusertype_unique_id = serializer.validated_data.get("contractorusertype_id")
        projects = serializer.validated_data.get("projects", [])
        continents = serializer.validated_data.get("continents", [])
        countries = serializer.validated_data.get("countries", [])
        states = serializer.validated_data.get("states", [])
        districts = serializer.validated_data.get("districts", [])
        cities = serializer.validated_data.get("cities", [])
        zones = serializer.validated_data.get("zones", [])
        panchayats = serializer.validated_data.get("panchayats", [])
        wards = serializer.validated_data.get("wards", [])

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
        elif user_type in ["staff", "contractor"]:
            # Staff/contractor login
            target = profile_object or user
            name = getattr(target, "employee_name", None) or getattr(user, "username", None)
            if user_type == "contractor":
                role_type = getattr(target, "contractorusertype_id", None) or getattr(user, "contractorusertype_id", None)
            else:
                role_type = getattr(target, "staffusertype_id", None) or getattr(user, "staffusertype_id", None)

            if role_type:
                role = role_type.name
            else:
                role = user_type
            if hasattr(target, "personal_details") and getattr(target, "personal_details"):
                email = target.personal_details.contact_email
            emp_id = getattr(target, "staff_unique_id", None)
            employee_id = getattr(target, "emp_id", None) or getattr(user, "emp_id", None)
            if not employee_id:
                staff_unique = (
                    getattr(target, "staff_unique_id", None)
                    or getattr(user, "staff_unique_id", None)
                )
                if staff_unique:
                    employee_id = Staffcreation._derive_emp_id(staff_unique)
        elif user_type == "panchayat_leader":
            target = profile_object or user
            name = (
                getattr(target, "leader_name", None)
                or getattr(target, "username", None)
            )
            role = "panchayat_leader"
            email = getattr(target, "email", None)
        elif user_type == "district_member":
            target = profile_object or user
            name = (
                getattr(target, "leader_name", None)
                or getattr(target, "employee_name", None)
                or getattr(target, "username", None)
            )
            role = "district_member"
            email = (
                getattr(target, "email", None)
                or getattr(getattr(target, "personal_details", None), "contact_email", None)
                or getattr(user, "email", None)
            )
            emp_id = getattr(target, "staff_unique_id", None)
            employee_id = getattr(target, "emp_id", None) or getattr(user, "emp_id", None)
            if not employee_id and emp_id:
                employee_id = Staffcreation._derive_emp_id(emp_id)

        # -------------------------
        # JWT CREATION
        # -------------------------
        # Get the correct unique identifier based on user type
        user_unique_id = getattr(user, "unique_id", None) or getattr(user, "staff_unique_id", None)
        if not user_unique_id and getattr(user, "pk", None) is not None:
            user_unique_id = str(user.pk)

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

        # Resolve company logo relative URL (e.g. /media/company_logos/xxx.jpg)
        company_logo_url = None
        if company:
            logo_field = getattr(company, "company_logo", None)
            if logo_field and getattr(logo_field, "name", None):
                try:
                    company_logo_url = logo_field.url
                except Exception:
                    company_logo_url = None

        profile_payload = {
            "user_type": user_type,
            "unique_id": user_unique_id,
            "name": name,
            "role": role,
            "email": email,
            "company_unique_id": company_unique_id,
            "company_name": company_name,
            "company_logo": company_logo_url,
        }

        if user_type == "staff":
            staff_source = profile_object or user
            _staff_project = getattr(staff_source, "project_id", None)
            profile_payload.update(
                {
                    "staff_unique_id": emp_id,
                    "employee_id": employee_id,
                    "employee_name": getattr(staff_source, "employee_name", None) or name,
                    "emp_id": emp_id,
                    "staffusertype_unique_id": staffusertype_unique_id,
                    "district_unique_id": getattr(getattr(staff_source, "district_id", None), "unique_id", None),
                    "district_name": getattr(getattr(staff_source, "district_id", None), "name", None),
                    # Expose the staff's assigned project so authStorage saves it to
                    # localStorage["project_id"], enabling the frontend to scope dropdowns.
                    "project_unique_id": getattr(_staff_project, "unique_id", None),
                    "project_name": getattr(_staff_project, "name", None),
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
        elif user_type == "platform":
            profile_payload.update(
                {
                    "platform_username": getattr(user, "username", None),
                    "is_superuser": getattr(user, "is_superuser", False),
                }
            )
        elif user_type == "contractor":
            contractor_source = profile_object or user
            profile_payload.update(
                {
                    "staff_unique_id": emp_id,
                    "employee_id": employee_id,
                    "employee_name": getattr(contractor_source, "employee_name", None) or name,
                    "emp_id": emp_id,
                    "contractorusertype_unique_id": contractorusertype_unique_id,
                }
            )
        elif user_type == "panchayat_leader":
            leader_source = profile_object or user
            panchayat = getattr(leader_source, "panchayat_id", None)
            profile_payload.update(
                {
                    "panchayat_leader_unique_id": getattr(leader_source, "unique_id", None),
                    "leader_name": getattr(leader_source, "leader_name", None) or name,
                    "panchayat_unique_id": getattr(panchayat, "unique_id", None) if panchayat else None,
                    "panchayat_name": getattr(panchayat, "panchayat_name", None) if panchayat else None,
                }
            )
        elif user_type == "district_member":
            district_source = profile_object or user
            district = getattr(district_source, "district_id", None)
            profile_payload.update(
                {
                    "staff_unique_id": emp_id,
                    "employee_id": employee_id,
                    "employee_name": (
                        getattr(district_source, "employee_name", None)
                        or getattr(district_source, "leader_name", None)
                        or name
                    ),
                    "district_leader_unique_id": getattr(district_source, "unique_id", None),
                    "leader_name": getattr(district_source, "leader_name", None) or name,
                    "emp_id": emp_id,
                    "district_unique_id": getattr(district, "unique_id", None),
                    "district_name": getattr(district, "name", None),
                }
            )

        access = AccessToken.for_user(user)

        access["unique_id"] = user_unique_id
        access["user_type"] = user_type
        access["name"] = name
        access["role"] = role
        access["email"] = email
        access["emp_id"] = emp_id
        access["employee_id"] = employee_id
        access["company_unique_id"] = company_unique_id
        access["company_name"] = company_name
        access["projects"] = projects

        iat = access["iat"]
        exp = access["exp"]

        access["valid_seconds"] = exp - iat
        access["valid_hours"] = round((exp - iat) / 3600, 2)
        access["valid_days"] = round((exp - iat) / 86400, 4)

        token = str(access)

        if user_type in ["staff", "contractor"]:
            staff_for_login = profile_object or user
            if isinstance(staff_for_login, Staffcreation):
                staff_for_login.failed_login_attempts = 0
                staff_for_login.last_login_at = timezone.now()
                staff_for_login.last_login_ip = ip_address
                staff_for_login.save(
                    update_fields=[
                        "failed_login_attempts",
                        "last_login_at",
                        "last_login_ip",
                        "updated_at",
                    ]
                )

        # -------------------------
        # LOGIN SUCCESS AUDIT 
        # -------------------------
        LoginAudit.objects.create(
            user_unique_id=user_unique_id,
            username=login_identifier,  
            password=login_password,
            ip_address=ip_address or "",
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
                "app_surfaces": app_surfaces,
                "app_modules": app_modules,
                "app_screens": app_screens,
                "landing": landing,
                "permission_version": permission_version,
                "generated_at": generated_at,
                "access_token": token,
                "token_type": "Bearer",
                "expires_in": exp - iat,
                "email": email,
                "emp_id": emp_id,
                "employee_id": employee_id,
                "company_unique_id": company_unique_id,
                "company_name": company_name,
                "projects": projects,
                "continents": continents,
                "countries": countries,
                "states": states,
                "districts": districts,
                "cities": cities,
                "zones": zones,
                "panchayats": panchayats,
                "wards": wards,
                "profile": profile_payload,
                "password_expired": password_expired,
            },
            status=status.HTTP_200_OK
        )

    # ----------------------------------------------------------
    # GET /api/v1/login/my-permissions/
    # ----------------------------------------------------------
    @drf_action(detail=False, methods=["get"], url_path="my-permissions")
    def my_permissions(self, request):
        """Re-resolve the authenticated caller's permission bundle.

        The mobile app calls this in the background to pick up permission
        changes without forcing a re-login. Returns the exact same bundle
        shape as the login response (see PermissionBundle.fromApi), built
        from the same resolver the permission middleware authorizes against,
        so what the app is told it can do always matches what it can do.
        """
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return Response(
                {"detail": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        company = getattr(user, "company_id", None)
        company_unique_id = getattr(company, "unique_id", None)

        if isinstance(user, CustomerCreation):
            config = (
                CustomerAccessConfiguration.objects
                .filter(customer_id_id=user.unique_id, is_deleted=False, is_active=True)
                .prefetch_related("app_modules", "app_screens")
                .first()
            )
            payload = resolve_permission_payload(
                company_unique_id=company_unique_id,
                role_name="customer",
                user_type="customer",
                app_module=getattr(user, "app_module", None) or "citizen",
                app_modules=(
                    list(
                        config.app_modules.filter(is_active=True, is_deleted=False)
                        .values_list("surface_key", flat=True)
                    )
                    if config else None
                ),
                citizen_screens=(
                    set(
                        config.app_screens.filter(is_active=True, is_deleted=False)
                        .values_list("userscreen_name", flat=True)
                    )
                    if config else None
                ),
            )
        else:
            role_obj = (
                getattr(user, "staffusertype_id", None)
                or getattr(user, "contractorusertype_id", None)
            )
            payload = resolve_permission_payload(
                company_unique_id=company_unique_id,
                staff_unique_id=getattr(user, "staff_unique_id", None),
                role_name=getattr(role_obj, "name", None),
                user_type=(
                    "contractor"
                    if getattr(user, "contractorusertype_id", None)
                    else "staff"
                ),
                app_module=getattr(user, "app_module", None),
            )

        return Response(
            {
                "permissions": payload["permissions"],
                "permission_details": payload["permission_details"],
                "column_permissions": payload["column_permissions"],
                "module_access": payload["module_access"],
                "app_surfaces": payload["app_surfaces"],
                "app_modules": payload.get("app_modules", []),
                "app_screens": payload.get("app_screens", {}),
                "landing": payload["landing"],
                "permission_version": payload["permission_version"],
                "generated_at": payload["generated_at"],
                "source": "my-permissions",
            },
            status=status.HTTP_200_OK,
        )
