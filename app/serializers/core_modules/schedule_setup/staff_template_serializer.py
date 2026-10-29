from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.serializers.superadmin.staff_management.user_serializer import UniqueIdOrPkField
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.utils.related_prefetch import prefetching_list_serializer, related

RELATED_LOOKUPS = {
    "company": (Company, "company_id"),
    "project": (Project, "project_id"),
    "driver": (Staffcreation, "driver_id", "staff_unique_id"),
    "operator": (Staffcreation, "operator_id", "staff_unique_id"),
}


class CommaSeparatedListField(serializers.ListField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            data = [x.strip() for x in data.split(",") if x.strip()]
        return super().to_internal_value(data)


class StaffTemplateSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    created_by = serializers.CharField(source="created_by_id", read_only=True)
    updated_by = serializers.CharField(source="updated_by_id", read_only=True)

    driver_id = NameOrUniqueIdField(
        slug_field="staff_unique_id",
        name_field="employee_name",
        queryset=Staffcreation.objects.filter(is_deleted=False)
    )

    operator_id = NameOrUniqueIdField(
        slug_field="staff_unique_id",
        name_field="employee_name",
        queryset=Staffcreation.objects.filter(is_deleted=False)
    )

    company_id = NameOrUniqueIdField(
        queryset=Company.objects.all(),
        name_field="name",
    )

    project_id = NameOrUniqueIdField(
        queryset=Project.objects.all(),
        name_field="name",
        scope_fields=["company_id"],
    )


    driver_name = serializers.SerializerMethodField()
    operator_name = serializers.SerializerMethodField()

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

    def get_company_name(self, obj):
        return getattr(related(obj, "company"), "name", None)

    def get_project_name(self, obj):
        return getattr(related(obj, "project"), "name", None)

    def get_driver_name(self, obj):
        return getattr(related(obj, "driver"), "employee_name", None)

    def get_operator_name(self, obj):
        return getattr(related(obj, "operator"), "employee_name", None)

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
        list_serializer_class = prefetching_list_serializer(RELATED_LOOKUPS)
