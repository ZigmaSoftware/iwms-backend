from rest_framework import serializers

from app.models.superadmin.staff_management.department import Department
from app.models.superadmin.staff_management.designation import Designation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.utils.related_prefetch import prefetching_list_serializer, related

RELATED_LOOKUPS = {
    "company": (Company, "company_id"),
    "project": (Project, "project_id"),
    "department": (Department, "department_id"),
}


class DesignationSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    status = serializers.ChoiceField(
        choices=(("active", "Active"), ("inactive", "Inactive")),
        write_only=True,
        required=False,
    )
    status_label = serializers.SerializerMethodField(read_only=True)
    department_id = NameOrUniqueIdField(
        name_field="department_name",
        queryset=Department.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    department_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Designation
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "department_id",
            "department_name",
            "designation_name",
            "designation_group",
            "description",
            "status",
            "status_label",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["unique_id", "id", "created_at", "updated_at", "is_deleted"]
        list_serializer_class = prefetching_list_serializer(RELATED_LOOKUPS)

    def get_company_name(self, obj):
        return getattr(related(obj, "company"), "name", None)

    def get_project_name(self, obj):
        return getattr(related(obj, "project"), "name", None)

    def get_status_label(self, obj):
        return "active" if obj.is_active else "inactive"

    def get_department_name(self, obj):
        department = related(obj, "department", Department, "department_id")
        return department.department_name if department else None

    def validate(self, attrs):
        status = attrs.pop("status", None)
        if status:
            attrs["is_active"] = status == "active"

        if attrs.get("designation_name"):
            attrs["designation_name"] = attrs["designation_name"].strip()
        if attrs.get("designation_group"):
            attrs["designation_group"] = attrs["designation_group"].strip()
        return attrs
