from rest_framework import serializers

from app.models.role_assigns.projectStaffHierarchy import ProjectStaffHierarchy
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.superadmin_masters.project import Project
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin


class ProjectStaffHierarchySerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    project_id = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.filter(is_deleted=False),
    )
    staffusertype_id = serializers.PrimaryKeyRelatedField(
        queryset=StaffUserType.objects.filter(is_deleted=False),
    )
    reports_to_staffusertype_id = serializers.PrimaryKeyRelatedField(
        queryset=StaffUserType.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )

    staffusertype_name = serializers.CharField(
        source="staffusertype_id.name", read_only=True
    )
    reports_to_staffusertype_name = serializers.CharField(
        source="reports_to_staffusertype_id.name", read_only=True
    )

    class Meta:
        model = ProjectStaffHierarchy
        fields = "__all__"
        read_only_fields = ["unique_id"]

    def validate(self, attrs):
        project = attrs.get("project_id", getattr(self.instance, "project_id", None))
        staffusertype = attrs.get("staffusertype_id", getattr(self.instance, "staffusertype_id", None))
        reports_to = attrs.get(
            "reports_to_staffusertype_id",
            getattr(self.instance, "reports_to_staffusertype_id", None),
        )

        if reports_to and staffusertype and reports_to.unique_id == staffusertype.unique_id:
            raise serializers.ValidationError(
                "A staff user type cannot report to itself."
            )

        if reports_to and project:
            seen = {staffusertype.unique_id} if staffusertype else set()
            current = reports_to
            while current is not None:
                if current.unique_id in seen:
                    raise serializers.ValidationError(
                        "This mapping creates a reporting cycle."
                    )
                seen.add(current.unique_id)
                next_entry = (
                    ProjectStaffHierarchy.objects.filter(
                        project_id=project,
                        staffusertype_id=current,
                        is_deleted=False,
                    )
                    .exclude(pk=getattr(self.instance, "pk", None))
                    .first()
                )
                current = next_entry.reports_to_staffusertype_id if next_entry else None

        return attrs
