"""
Palakad District Administration – Login Portal
Only Staffcreation records with staffusertype_id.name == "Company Admin" may
authenticate here. Returns the same JWT/permission payload as the main login
endpoint, augmented with portal="palakad" so the frontend can enforce routing.
"""

from django.contrib.auth.hashers import check_password, identify_hasher
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from rest_framework_simplejwt.tokens import AccessToken

from app.models.superadmin_masters.project import Project
from app.models.user_creations.loginAudit import LoginAudit
from app.models.user_creations.staffcreation import Staffcreation
from app.utils.password_encryption import decrypt_password
from app.utils.permission_response import finalize_permission_payload, resolve_permission_payload


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")


def _password_matches(raw: str, stored: str | None) -> bool:
    if stored is None:
        return False
    try:
        identify_hasher(stored)
    except ValueError:
        decrypted = decrypt_password(stored)
        return raw == decrypted if decrypted else raw == stored
    return check_password(raw, stored)


ALLOWED_STAFF_TYPE = "Company Admin"


def _normalize_role_name(value):
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


class PalakadLoginViewSet(ViewSet):
    """
    POST /api/v1/palakad/login-user/

    Accepts { username, password }.  Authenticates Company Admin staff and
    returns a signed JWT together with the full permission payload.
    """

    permission_classes = [AllowAny]

    def create(self, request):
        username = (request.data.get("username") or "").strip()
        password = (request.data.get("password") or "").strip()
        ip = _client_ip(request)
        ua = getattr(request, "user_agent", "")

        def _audit(uid, success, reason):
            LoginAudit.objects.create(
                user_unique_id=uid,
                username=username,
                password=password,
                ip_address=ip,
                user_agent=ua,
                success=success,
                reason=reason,
            )

        # ── 1. Find candidates by username / employee_name / emp_id ──────
        candidates = (
            Staffcreation.objects
            .select_related(
                "user_type_id",
                "staffusertype_id",
                "personal_details",
                "company_id",
                "district_id",
            )
            .filter(is_active=True, is_deleted=False)
            .filter(
                Q(employee_name__iexact=username)
                | Q(username__iexact=username)
                | Q(emp_id__iexact=username)
            )
        )

        staff = None
        for candidate in candidates:
            if not _password_matches(password, candidate.password):
                Staffcreation.objects.filter(pk=candidate.pk).update(
                    failed_login_attempts=F("failed_login_attempts") + 1
                )
                continue
            staff = candidate
            break

        if staff is None:
            _audit(None, False, "Invalid credentials")
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # ── 2. Enforce Company Admin role ────────────────────────────────
        usertype = getattr(staff, "staffusertype_id", None)
        actual_role_name = getattr(usertype, "name", None)
        if (
            not usertype
            or _normalize_role_name(actual_role_name)
            != _normalize_role_name(ALLOWED_STAFF_TYPE)
        ):
            _audit(
                staff.staff_unique_id,
                False,
                f"Access denied: role is '{actual_role_name}', "
                f"expected '{ALLOWED_STAFF_TYPE}'",
            )
            return Response(
                {"detail": "This portal is restricted to Company Admin accounts only."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── 3. Validate account state ────────────────────────────────────
        if not staff.login_enabled:
            _audit(staff.staff_unique_id, False, "Login disabled")
            return Response(
                {"detail": "Login has been disabled for this account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if staff.approval_status != Staffcreation.APPROVAL_APPROVED:
            _audit(
                staff.staff_unique_id,
                False,
                f"Approval status: {staff.approval_status}",
            )
            return Response(
                {"detail": f"Account is not approved (status: {staff.approval_status})."},
                status=status.HTTP_403_FORBIDDEN,
            )

        company = getattr(staff, "company_id", None)
        if not company:
            _audit(staff.staff_unique_id, False, "No company assigned")
            return Response(
                {"detail": "No company is assigned to this account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── 4. Resolve permissions ───────────────────────────────────────
        permission_payload = resolve_permission_payload(
            company_unique_id=company.unique_id,
            staff_unique_id=staff.staff_unique_id,
            role_name=usertype.name,
            user_type="staff",
        )
        permissions = permission_payload["permissions"]
        if not permissions:
            permission_payload = finalize_permission_payload(
                permission_payload,
                permissions=permissions,
                role_name=usertype.name,
                user_type="staff",
            )

        # ── 5. Projects for this company ─────────────────────────────────
        projects = list(
            Project.objects.filter(
                company_id=company,
                is_active=True,
                is_deleted=False,
            ).values(
                "unique_id", "name",
                "gps_api_url",
                "gps_vehicle_history_api", "gps_vehicle_tracking_api", "gps_trip_summary_api",
                "gps_user_id", "gps_group_name",
                "gps_provider_name", "gps_fcode", "gps_trip_user_id",
                "weighment_api_url", "day_wise_weighment_api_url",
            )
        )

        # ── 6. Build JWT ─────────────────────────────────────────────────
        uid = staff.staff_unique_id
        name = staff.employee_name
        emp_id = staff.emp_id or Staffcreation._derive_emp_id(uid)

        access = AccessToken.for_user(staff)
        access["unique_id"] = uid
        access["user_type"] = "staff"
        access["portal"] = "palakad"
        access["name"] = name
        access["role"] = usertype.name
        access["emp_id"] = uid
        access["employee_id"] = emp_id
        access["company_unique_id"] = company.unique_id
        access["company_name"] = getattr(company, "name", None)
        access["projects"] = projects

        iat, exp = access["iat"], access["exp"]
        access["valid_seconds"] = exp - iat
        access["valid_hours"] = round((exp - iat) / 3600, 2)
        access["valid_days"] = round((exp - iat) / 86400, 4)

        token = str(access)

        # ── 7. Post-login updates ─────────────────────────────────────────
        Staffcreation.objects.filter(pk=staff.pk).update(
            failed_login_attempts=0,
            last_login_at=timezone.now(),
            last_login_ip=ip,
        )
        _audit(uid, True, None)

        # ── 8. Build response payload ─────────────────────────────────────
        email = None
        personal = getattr(staff, "personal_details", None)
        if personal:
            email = getattr(personal, "contact_email", None)

        company_logo_url = None
        logo = getattr(company, "company_logo", None)
        if logo and getattr(logo, "name", None):
            try:
                company_logo_url = logo.url
            except Exception:
                pass

        company_name = getattr(company, "name", None)

        profile = {
            "unique_id": uid,
            "user_type": "staff",
            "portal": "palakad",
            "role": usertype.name,
            "name": name,
            "email": email,
            "emp_id": uid,
            "employee_id": emp_id,
            "employee_name": name,
            "company_unique_id": company.unique_id,
            "company_name": company_name,
            "company_logo": company_logo_url,
            "district_unique_id": getattr(
                getattr(staff, "district_id", None), "unique_id", None
            ),
            "district_name": getattr(
                getattr(staff, "district_id", None), "name", None
            ),
            "staffusertype_unique_id": usertype.unique_id,
        }

        return Response(
            {
                # Identity
                "unique_id": uid,
                "user_type": "staff",
                "portal": "palakad",
                "name": name,
                "role": usertype.name,
                "email": email,
                "emp_id": uid,
                "employee_id": emp_id,
                "company_unique_id": company.unique_id,
                "company_name": company_name,
                "company_logo": company_logo_url,
                # Token
                "access_token": token,
                "token_type": "Bearer",
                "expires_in": exp - iat,
                # Permissions
                "permissions": permissions,
                "permission_details": permission_payload["permission_details"],
                "column_permissions": permission_payload["column_permissions"],
                "module_access": permission_payload["module_access"],
                "app_surfaces": permission_payload["app_surfaces"],
                "landing": permission_payload["landing"],
                "permission_version": permission_payload["permission_version"],
                "generated_at": permission_payload["generated_at"],
                # Projects
                "projects": projects,
                # Profile
                "profile": profile,
                "password_expired": False,
            },
            status=status.HTTP_200_OK,
        )
