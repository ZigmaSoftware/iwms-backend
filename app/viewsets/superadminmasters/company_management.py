from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.user_creations.staffcreation import StaffOfficeDetails, StaffPersonalDetails
from app.models.role_assigns.userType import UserType
from app.models.role_assigns.staffUserType import StaffUserType
from app.permissions.platform import PlatformSuperAdminOnly
from app.serializers.superadmin_masters.company_create_serializer import PlatformCompanyCreateSerializer


@method_decorator(csrf_exempt, name='dispatch')
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
        project = Project.objects.create(
            name=f"{company.name} Main Project",
            company_id=company,
            description=f"Default project for {company.name}",
            is_active=True,
            is_deleted=False,
        )

        # Global user type rows (kept global even though tenancy columns exist).
        staff_type, _ = UserType.objects.get_or_create(name="staff", defaults={"is_active": True, "is_deleted": False})

        # Global staff role rows.
        admin_role, _ = StaffUserType.objects.get_or_create(
            usertype_id=staff_type,
            name="admin",
            defaults={"is_active": True, "is_deleted": False},
        )

        # Create staff with auth fields directly (no separate User model)
        staff = StaffOfficeDetails.objects.create(
            company_id=company,
            project_id=project,
            employee_name=data["admin_employee_name"],
            username=data["admin_username"],
            password=data["admin_password"],
            user_type_id=staff_type,
            staffusertype_id=admin_role,
            is_staff=False,
            is_active=True,
            is_deleted=False,
        )

        email = data.get("admin_email")
        if email:
            StaffPersonalDetails.objects.create(
                company_id=company,
                project_id=project,
                staff=staff,
                staff_unique_id=staff.staff_unique_id,
                contact_email=email,
            )

        return Response(
            {
                "company": {"unique_id": company.unique_id, "name": company.name},
                "company_admin": {"unique_id": staff.staff_unique_id, "username": staff.username},
            },
            status=status.HTTP_201_CREATED,
        )
