from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

from app.models.customers.customercreation import CustomerCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.utils.permission_response import resolve_permission_payload


class PermissionViewSet(ViewSet):
    """
    Fetch current user's permissions dynamically from DB.
    Works with custom Staffcreation model (no dependency on Django User).
    """

    def list(self, request):
        """
        GET /api/v1/my-permissions/
        Returns latest permissions for current user.
        """
        payload = self._resolve_permission_payload_for_user(request.user)

        return Response(
            {
                "permissions": payload.get("permissions", {}),
                "permission_details": payload.get("permission_details", {}),
                "column_permissions": payload.get("column_permissions", {}),
                "module_access": payload.get("module_access", []),
                "app_surfaces": payload.get("app_surfaces", []),
                "landing": payload.get("landing"),
                "permission_version": payload.get("permission_version"),
                "generated_at": payload.get("generated_at"),
                "timestamp": timezone.now().isoformat(),
                "source": "database"
            },
            status=status.HTTP_200_OK
        )

    # ------------------------------------------------------------------
    # CORE LOGIC
    # ------------------------------------------------------------------

    def _resolve_permission_payload_for_user(self, user):
        if getattr(user, "is_superuser", False):
            return resolve_permission_payload(
                include_all=True,
                role_name="superadmin",
                user_type="platform",
            )

        staff_user = self._resolve_staff_user(user)
        if staff_user:
            company = getattr(staff_user, "company_id", None)
            user_type = getattr(staff_user, "user_type_id", None)
            staff_usertype = getattr(staff_user, "staffusertype_id", None)
            contractor_usertype = getattr(staff_user, "contractorusertype_id", None)

            if not company or not user_type:
                return {}

            role_name = (
                getattr(staff_usertype, "name", None)
                or getattr(contractor_usertype, "name", None)
                or getattr(user_type, "name", None)
            )
            return resolve_permission_payload(
                company_unique_id=company.unique_id,
                staff_unique_id=getattr(staff_user, "staff_unique_id", None),
                role_name=role_name,
                user_type=getattr(user_type, "name", None),
            )

        customer_user = self._resolve_customer_user(user)
        if customer_user:
            company = getattr(customer_user, "company_id", None)
            user_type = getattr(customer_user, "user_type_id", None)
            if not company or not user_type:
                return {}

            return resolve_permission_payload(
                company_unique_id=company.unique_id,
                role_name="customer",
                user_type=getattr(user_type, "name", None),
            )

        return {}

    def _resolve_permission_details_for_user(self, user):
        if getattr(user, "is_superuser", False):
            return resolve_permission_payload(include_all=True)["permission_details"]

        staff_user = self._resolve_staff_user(user)
        if not staff_user:
            return {}

        company = getattr(staff_user, "company_id", None)
        user_type = getattr(staff_user, "user_type_id", None)

        if not company or not user_type:
            return {}

        return resolve_permission_payload(
            company_unique_id=company.unique_id,
            staff_unique_id=getattr(staff_user, "staff_unique_id", None),
        )["permission_details"]

    def _resolve_column_permissions_for_user(self, user):
        if getattr(user, "is_superuser", False):
            return resolve_permission_payload(include_all=True)["column_permissions"]

        staff_user = self._resolve_staff_user(user)
        if not staff_user:
            return {}

        company = getattr(staff_user, "company_id", None)
        user_type = getattr(staff_user, "user_type_id", None)

        if not company or not user_type:
            return {}

        return resolve_permission_payload(
            company_unique_id=company.unique_id,
            staff_unique_id=getattr(staff_user, "staff_unique_id", None),
        )["column_permissions"]

    # ------------------------------------------------------------------
    # STAFF RESOLVER
    # ------------------------------------------------------------------

    def _resolve_staff_user(self, user):
        """
        Extract Staffcreation object from various user representations.
        """

        # Case 1: user itself is Staffcreation
        if isinstance(user, Staffcreation):
            return user

        # Case 2: user has staff relation
        staff = getattr(user, "staff", None)
        if staff:
            return staff
        staff = getattr(user, "staff_id", None)
        if staff:
            return staff

        # Case 3: try lookup using unique_id (from JWT)
        user_unique_id = None

        if hasattr(user, "unique_id"):
            user_unique_id = user.unique_id
        elif hasattr(user, "staff_unique_id"):
            user_unique_id = user.staff_unique_id

        if user_unique_id:
            try:
                return Staffcreation.objects.filter(
                    staff_unique_id=user_unique_id
                ).first()
            except Exception:
                return None

        return None

    def _resolve_customer_user(self, user):
        if isinstance(user, CustomerCreation):
            return user

        customer = getattr(user, "customer", None)
        if customer:
            return customer
        customer = getattr(user, "customer_id", None)
        if customer:
            return customer

        user_unique_id = getattr(user, "unique_id", None)
        if user_unique_id:
            return CustomerCreation.objects.filter(unique_id=user_unique_id).first()

        return None

