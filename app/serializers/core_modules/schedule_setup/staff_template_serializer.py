from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.staff_creations.staffcreation import Staffcreation
from app.serializers.superadmin.staff_management.user_serializer import UniqueIdOrPkField
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class CommaSeparatedListField(serializers.ListField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            data = [x.strip() for x in data.split(",") if x.strip()]
        return super().to_internal_value(data)


class StaffTemplateSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    driver_id = UniqueIdOrPkField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False)
    )

    operator_id = UniqueIdOrPkField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False)
    )

    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all()
    )

    project_id = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all()
    )


    driver_name = serializers.CharField(source="driver_id.employee_name", read_only=True)
    operator_name = serializers.CharField(source="operator_id.employee_name", read_only=True)

    extra_operator_id = CommaSeparatedListField(
        child=serializers.CharField(),
        required=False
    )

    staffusertype_name = serializers.CharField(
        source="staffusertype_id.name",
        read_only=True
    )

    is_assigned_today = serializers.SerializerMethodField()

    def get_is_assigned_today(self, obj):
        return bool(getattr(obj, "is_assigned_today", False))

    class Meta:
        model = StaffTemplate
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",

            "display_code",

            "driver_id",
            "driver_name",
            # "driver_role",

            "operator_id",
            "operator_name",
            # "operator_role",

            "extra_operator_id",

            "staffusertype_name",

            "created_by",


            "updated_by",


            "status",

            "created_at",
            "updated_at",
            "is_active",
            "is_deleted",
            "is_assigned_today",
        ]

        read_only_fields = [
            "unique_id",
            "display_code",
            "created_at",
            "updated_at",
            "driver_name",
            "operator_name",
            "driver_role",
            "operator_role",
            "created_by_name",
            "updated_by_name",
        ]