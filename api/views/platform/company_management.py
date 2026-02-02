from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.apps.company import Company
from api.apps.staffcreation import StaffOfficeDetails, StaffPersonalDetails
from api.apps.userType import UserType
from api.apps.staffUserType import StaffUserType
from api.permissions.platform import PlatformSuperAdminOnly
from api.serializers.platform.company_create_serializer import PlatformCompanyCreateSerializer


class PlatformCompanyCreateView(APIView):
    permission_classes = [PlatformSuperAdminOnly]

    @transaction.atomic
    def post(self, request):
        serializer = PlatformCompanyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        company = Company.objects.create(
            name=data["name"],
            description=data.get("description"),
        )

        # Global user type rows (kept global even though tenancy columns exist).
        staff_type, _ = UserType.objects.get_or_create(name="staff", defaults={"is_active": True, "is_deleted": False})

        # Global staff role rows.
        admin_role, _ = StaffUserType.objects.get_or_create(
            usertype_id=staff_type,
            name="admin",
            defaults={"is_active": True, "is_deleted": False},
        )

        staff = StaffOfficeDetails.objects.create(
            company_id=company,
            employee_name=data["admin_employee_name"],
        )

        email = data.get("admin_email")
        if email:
            StaffPersonalDetails.objects.create(
                company_id=company,
                staff=staff,
                staff_unique_id=staff.staff_unique_id,
                contact_email=email,
            )

        User = get_user_model()
        admin_user = User.objects.create_user(
            username=data["admin_username"],
            password=data["admin_password"],
            company_id=company,
            user_type_id=staff_type,
            staffusertype_id=admin_role,
            staff_id=staff,
            is_staff=False,
            is_active=True,
            is_deleted=False,
        )

        return Response(
            {
                "company": {"unique_id": company.unique_id, "name": company.name},
                "company_admin": {"unique_id": admin_user.unique_id, "username": admin_user.username},
            },
            status=status.HTTP_201_CREATED,
        )
