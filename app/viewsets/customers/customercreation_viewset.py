from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.customers.customercreation import CustomerCreation
from app.models.superadmin_masters.project import Project
from app.serializers.customers.customercreation_serializer import CustomerCreationSerializer


class CustomerCreationViewSet(CompanyScopedViewSet):
    permission_resource = "CustomerCreation"
    serializer_class = CustomerCreationSerializer
    lookup_field = "unique_id"

    queryset = (
        CustomerCreation.objects
        .filter(is_deleted=False)
        .select_related(
            "company_id",
            "project_id",
            "ward",
            "zone",
            "city",
            "district",
            "state",
            "country",
            "panchayat_id",
            "property_ref",
            "sub_property",
            # "is_bulkwaste_generator"
        )
        .order_by("customer_name")
    )

    # -----------------------------------------------------
    # Resolve default project
    # -----------------------------------------------------

    def _resolve_default_project(self):
        company = self._company()
        if not company:
            return None

        user = getattr(self.request, "user", None)
        user_project = getattr(user, "project_id", None)

        if user_project and getattr(user_project, "company_id", None) == company:
            return user_project

        payload = getattr(self.request, "jwt_payload", {}) or {}
        project_unique_id = payload.get("project_unique_id")

        if not project_unique_id:
            return None

        return Project.objects.filter(
            unique_id=project_unique_id,
            company_id=company,
        ).first()

    # -----------------------------------------------------
    # Project Resolver
    # -----------------------------------------------------

    def _project(self):
        project = super()._project()

        if project is not None:
            return project

        if self.request.method in ("POST", "PUT", "PATCH"):
            return self._resolve_default_project()

        return None