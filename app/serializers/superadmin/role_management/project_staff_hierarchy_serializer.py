from rest_framework import serializers

from app.models.role_assigns.projectStaffHierarchy import ProjectStaffHierarchy
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.superadmin_masters.project import Project
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.superadmin.staff_management.user_serializer import UniqueIdOrPkField


class ProjectStaffHierarchySerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    project_id = UniqueIdOrPkField(
        queryset=Project.objects.filter(is_deleted=False),
    )
    staffusertype_id = UniqueIdOrPkField(
        queryset=StaffUserType.objects.filter(is_deleted=False),
    )
    reports_to_staffusertype_id = UniqueIdOrPkField(
        queryset=StaffUserType.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )

    project_name = serializers.SerializerMethodField()
    staffusertype_name = serializers.SerializerMethodField()
    reports_to_staffusertype_name = serializers.SerializerMethodField()

    class Meta:
        model = ProjectStaffHierarchy
        fields = "__all__"
        read_only_fields = ["unique_id"]

    def get_project_name(self, obj):
        project = Project.objects.filter(unique_id=obj.project_id).only("name").first()
        return project.name if project else None

    def get_staffusertype_name(self, obj):
        staffusertype = StaffUserType.objects.filter(unique_id=obj.staffusertype_id).only("name").first()
        return staffusertype.name if staffusertype else None

    def get_reports_to_staffusertype_name(self, obj):
        staffusertype = StaffUserType.objects.filter(
            unique_id=obj.reports_to_staffusertype_id,
        ).only("name").first()
        return staffusertype.name if staffusertype else None

    def validate(self, attrs):
        project = attrs.get("project_id", getattr(self.instance, "project_id", None))
        staffusertype = attrs.get("staffusertype_id", getattr(self.instance, "staffusertype_id", None))
        reports_to = attrs.get(
            "reports_to_staffusertype_id",
            getattr(self.instance, "reports_to_staffusertype_id", None),
        )

        if reports_to and staffusertype and reports_to == staffusertype:
            raise serializers.ValidationError(
                "A staff user type cannot report to itself."
            )

        if reports_to and project:
            seen = {staffusertype} if staffusertype else set()
            current = reports_to
            while current is not None:
                if current in seen:
                    raise serializers.ValidationError(
                        "This mapping creates a reporting cycle."
                    )
                seen.add(current)
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
