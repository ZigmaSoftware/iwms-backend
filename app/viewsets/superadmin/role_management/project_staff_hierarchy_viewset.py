from rest_framework import viewsets

from app.models.role_assigns.projectStaffHierarchy import ProjectStaffHierarchy
from app.serializers.superadmin.role_management.project_staff_hierarchy_serializer import (
    ProjectStaffHierarchySerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.filters import ModelFieldQueryFilter


class ProjectStaffHierarchyViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    pagination_class = None
    queryset = ProjectStaffHierarchy.objects.filter(is_deleted=False).select_related(
        "project_id", "staffusertype_id", "reports_to_staffusertype_id"
    )
    serializer_class = ProjectStaffHierarchySerializer
    lookup_field = "unique_id"
    filter_backends = [ModelFieldQueryFilter]

    AUDIT_MODULE = "role-assigns"
    AUDIT_ENDPOINT = "project-staff-hierarchy"

    permission_resource = "ProjectStaffHierarchy"

    def perform_destroy(self, instance):
        instance.delete()
