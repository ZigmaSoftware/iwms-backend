from django.db import transaction
from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.superadmin.staff_management.staffcreation import Staffcreation, StaffPersonalDetails


def _is_platform_super_admin(user):
    return bool(
        user
        and user.is_authenticated
        and getattr(user, "is_superuser", False)
        and getattr(user, "company_id", None) is None
    )


def _resolve_project_company(project):
    if not project.company_id:
        return None
    return (
        Company.objects.filter(Q(unique_id=project.company_id) | Q(name=project.company_id))
        .only("unique_id", "name")
        .first()
    )


class ProjectCreateSerializer(serializers.ModelSerializer):
    company_unique_id = serializers.CharField(max_length=30, required=False, write_only=True)
    admin_username = serializers.CharField(max_length=150, required=False, write_only=True)
    admin_password = serializers.CharField(write_only=True, min_length=8, required=False)
    admin_employee_name = serializers.CharField(max_length=200, required=False, write_only=True)
    admin_email = serializers.EmailField(required=False, allow_null=True, allow_blank=True, write_only=True)
    created_by = serializers.CharField(source="created_by_id", read_only=True)
    updated_by = serializers.CharField(source="updated_by_id", read_only=True)
    attendance_api_configured = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Project
        fields = [
            "company_unique_id",
            "name",
            "description",
            "project_logo",
            "gps_api_url",
            "gps_vehicle_history_api",
            "gps_vehicle_tracking_api",
            "gps_trip_summary_api",
            "gps_user_id",
            "gps_group_name",
            "gps_provider_name",
            "gps_fcode",
            "gps_trip_user_id",
            "weighment_api_url",
            "day_wise_weighment_api_url",
            "attendance_api_url",
            "attendance_api_key",
            "attendance_api_configured",
            "admin_username",
            "admin_password",
            "admin_employee_name",
            "admin_email",
            "created_by",
            "updated_by",
        ]
        extra_kwargs = {
            "attendance_api_key": {
                "write_only": True,
                "required": False,
                "allow_blank": True,
            },
        }

    def get_attendance_api_configured(self, obj):
        return bool(obj.attendance_api_url and obj.attendance_api_key)

    def _resolve_company(self, user, company_unique_id, is_platform_super_admin):
        user_company = getattr(user, "company_id", None)

        if is_platform_super_admin:
            if not company_unique_id:
                raise ValidationError({"company_unique_id": "company_unique_id is required for platform super admin"})
            company = Company.objects.filter(unique_id=company_unique_id).first()
            if not company:
                raise ValidationError({"company_unique_id": "Invalid company_unique_id"})
            return company

        if not user_company:
            raise PermissionDenied("User is not attached to a company")

        if company_unique_id and company_unique_id != getattr(user_company, "unique_id", None):
            raise PermissionDenied("company_unique_id does not match the authenticated company")

        return user_company

    @staticmethod
    def _has_all_admin_fields(admin_username, admin_password, admin_employee_name):
        return bool(admin_username and admin_password and admin_employee_name)

    def _validate_admin_payload(
        self,
        *,
        has_existing_project,
        is_platform_super_admin,
        admin_username,
        admin_password,
        admin_employee_name,
        admin_email,
    ):
        required_fields = (admin_username, admin_password, admin_employee_name)
        has_any_admin_fields = any([*required_fields, admin_email])
        has_all_admin_fields = self._has_all_admin_fields(admin_username, admin_password, admin_employee_name)

        if has_existing_project and has_any_admin_fields:
            raise ValidationError({"admin_username": "Admin credentials are only allowed while creating first project"})

        if not has_existing_project and is_platform_super_admin and not has_all_admin_fields:
            raise ValidationError(
                {
                    "admin_username": "admin_username, admin_password, and admin_employee_name are required for first project",
                }
            )

        if has_any_admin_fields and not has_all_admin_fields:
            raise ValidationError(
                {
                    "admin_username": "admin_username, admin_password, and admin_employee_name must be provided together",
                }
            )

    @staticmethod
    def _create_project_admin(company, project, admin_username, admin_password, admin_employee_name, admin_email):
        staff_type, _ = UserType.objects.get_or_create(
            name="staff",
            defaults={"is_active": True, "is_deleted": False},
        )
        admin_role, _ = StaffUserType.objects.get_or_create(
            usertype_id=staff_type.unique_id,
            name="admin",
            defaults={"is_active": True, "is_deleted": False},
        )

        staff = Staffcreation.objects.create(
            company_id=company.unique_id,
            project_id=project.unique_id,
            employee_name=admin_employee_name,
            username=admin_username,
            password=admin_password,
            user_type_id=staff_type.unique_id,
            staffusertype_id=admin_role.unique_id,
            is_staff=False,
            is_active=True,
            is_deleted=False,
        )

        if admin_email:
            StaffPersonalDetails.objects.create(
                company_id=company.unique_id,
                project_id=project.unique_id,
                staff=staff,
                staff_unique_id=staff.staff_unique_id,
                contact_email=admin_email,
            )
        return staff

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        company_unique_id = validated_data.pop("company_unique_id", None)
        admin_username = validated_data.pop("admin_username", None)
        admin_password = validated_data.pop("admin_password", None)
        admin_employee_name = validated_data.pop("admin_employee_name", None)
        admin_email = validated_data.pop("admin_email", None)
        created_by_id = validated_data.get("created_by_id")
        updated_by_id = validated_data.get("updated_by_id")

        is_platform_super_admin = _is_platform_super_admin(user)
        company = self._resolve_company(user, company_unique_id, is_platform_super_admin)

        has_existing_project = Project.objects.filter(company_id=company.unique_id, is_deleted=False).exists()
        self._validate_admin_payload(
            has_existing_project=has_existing_project,
            is_platform_super_admin=is_platform_super_admin,
            admin_username=admin_username,
            admin_password=admin_password,
            admin_employee_name=admin_employee_name,
            admin_email=admin_email,
        )

        project = Project.objects.create(
            company_id=company.unique_id,
            name=validated_data["name"],
            description=validated_data.get("description"),
            project_logo=validated_data.get("project_logo"),
            gps_api_url=validated_data.get("gps_api_url"),
            gps_vehicle_history_api=validated_data.get("gps_vehicle_history_api"),
            gps_vehicle_tracking_api=validated_data.get("gps_vehicle_tracking_api"),
            gps_trip_summary_api=validated_data.get("gps_trip_summary_api"),
            gps_user_id=validated_data.get("gps_user_id", "BLUEPLANET"),
            gps_group_name=validated_data.get("gps_group_name", "BLUEPLANET:VAM"),
            gps_provider_name=validated_data.get("gps_provider_name", "BLUEPLANET"),
            gps_fcode=validated_data.get("gps_fcode", "VAM"),
            gps_trip_user_id=validated_data.get("gps_trip_user_id", "NMCP2DISPOSAL"),
            weighment_api_url=validated_data.get("weighment_api_url"),
            day_wise_weighment_api_url=validated_data.get("day_wise_weighment_api_url"),
            attendance_api_url=validated_data.get("attendance_api_url"),
            attendance_api_key=validated_data.get("attendance_api_key"),
            is_active=True,
            is_deleted=False,
            created_by_id=created_by_id,
            updated_by_id=updated_by_id,
        )

        self._company_admin_payload = None
        if not has_existing_project and self._has_all_admin_fields(
            admin_username,
            admin_password,
            admin_employee_name,
        ):
            staff = self._create_project_admin(
                company,
                project,
                admin_username,
                admin_password,
                admin_employee_name,
                admin_email,
            )
            self._company_admin_payload = {
                "unique_id": staff.staff_unique_id,
                "username": staff.username,
            }

        return project

    def to_representation(self, instance):
        project_data = ProjectSerializer(instance, context=self.context).data
        view = self.context.get("view")
        if view and getattr(view, "action", None) != "create":
            return project_data

        payload = {"project": project_data}
        company_admin = getattr(self, "_company_admin_payload", None)
        if company_admin:
            payload["company_admin"] = company_admin
        return payload


class ProjectUpdateSerializer(serializers.ModelSerializer):
    company_unique_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    created_by = serializers.CharField(source="created_by_id", read_only=True)
    updated_by = serializers.CharField(source="updated_by_id", read_only=True)
    attendance_api_configured = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "unique_id",
            "company_unique_id",
            "company_name",
            "name",
            "description",
            "project_logo",
            "gps_api_url",
            "gps_vehicle_history_api",
            "gps_vehicle_tracking_api",
            "gps_trip_summary_api",
            "gps_user_id",
            "gps_group_name",
            "gps_provider_name",
            "gps_fcode",
            "gps_trip_user_id",
            "weighment_api_url",
            "day_wise_weighment_api_url",
            "attendance_api_url",
            "attendance_api_key",
            "attendance_api_configured",
            "is_active",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["unique_id", "company_unique_id", "company_name", "created_by", "updated_by"]
        extra_kwargs = {
            "attendance_api_key": {
                "write_only": True,
                "required": False,
                "allow_blank": True,
            },
        }

    def get_attendance_api_configured(self, obj):
        return bool(obj.attendance_api_url and obj.attendance_api_key)

    def get_company_unique_id(self, obj):
        company = _resolve_project_company(obj)
        return company.unique_id if company else obj.company_id

    def get_company_name(self, obj):
        company = _resolve_project_company(obj)
        return company.name if company else None

    def update(self, instance, validated_data):
        # Keep legacy behavior: PUT without description clears description.
        if not self.partial and "description" not in validated_data:
            validated_data["description"] = None
        return super().update(instance, validated_data)


class ProjectSerializer(serializers.ModelSerializer):
    company_unique_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    created_by = serializers.CharField(source="created_by_id", read_only=True)
    updated_by = serializers.CharField(source="updated_by_id", read_only=True)
    attendance_api_configured = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "unique_id",
            "company_unique_id",
            "company_name",
            "name",
            "description",
            "project_logo",
            "gps_api_url",
            "gps_vehicle_history_api",
            "gps_vehicle_tracking_api",
            "gps_trip_summary_api",
            "gps_user_id",
            "gps_group_name",
            "gps_provider_name",
            "gps_fcode",
            "gps_trip_user_id",
            "weighment_api_url",
            "day_wise_weighment_api_url",
            "attendance_api_url",
            "attendance_api_configured",
            "is_active",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "unique_id",
            "company_unique_id",
            "company_name",
            "is_active",
            "created_by",
            "updated_by",
        ]

    def get_attendance_api_configured(self, obj):
        return bool(obj.attendance_api_url and obj.attendance_api_key)

    def get_company_unique_id(self, obj):
        company = _resolve_project_company(obj)
        return company.unique_id if company else obj.company_id

    def get_company_name(self, obj):
        company = _resolve_project_company(obj)
        return company.name if company else None
