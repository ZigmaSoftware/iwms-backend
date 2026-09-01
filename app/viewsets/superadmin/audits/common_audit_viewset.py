from rest_framework import filters, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.utils.audit_context import (
    is_platform_super_admin,
    resolve_actor,
    resolve_tenancy,
)
from app.utils.common_audit import CommonAudit
from app.utils.pagination import LimitOffsetWithPage
from app.serializers.superadmin.audits.common_audit_serializer import (
    CommonAuditSerializer,
)


class CommonAuditViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Enterprise-wide audit trail.

    Append-only: PATCH/PUT/DELETE are deliberately not routed, since an
    audit log that callers can rewrite or erase is not evidence of
    anything. CREATE stays available for manual events that no viewset
    write hook can observe (Excel template downloads, bulk exports); the
    actor and tenancy on those are resolved server-side, never trusted
    from the payload.
    """

    permission_classes = [IsAuthenticated]

    queryset = CommonAudit.objects.all().order_by("-createdAt")
    serializer_class = CommonAuditSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = [
        "module_name",
        "endpoint_name",
        "createdBy",
        "created_by_name",
        "created_by_id",
        "object_id",
        "company_name",
        "project_name",
    ]
    ordering_fields = ["createdAt", "module_name", "company_name", "project_name"]

    def perform_create(self, serializer):
        """
        Stamp actor and tenancy from the request, so a client cannot forge
        who did it or file the entry under another company.
        """
        user = self.request.user
        created_by_id, created_by_name, created_by_type = resolve_actor(user)
        scope, company_uid, company_name, project_uid, project_name = resolve_tenancy(
            user, None
        )

        serializer.save(
            scope=scope,
            company_unique_id=company_uid,
            company_name=company_name,
            project_unique_id=project_uid,
            project_name=project_name,
            createdBy=str(user),
            created_by_id=created_by_id,
            created_by_name=created_by_name,
            created_by_type=created_by_type,
        )

    def _scoped_base_queryset(self):
        """
        Tenancy gate. A platform super admin sees the whole enterprise; a
        company user is confined to their own company's rows, enforced here
        rather than relying on the UI to omit the filter.
        """
        queryset = CommonAudit.objects.all().order_by("-createdAt")
        user = self.request.user

        if is_platform_super_admin(user):
            return queryset

        company = getattr(user, "company_id", None)
        company_uid = str(getattr(company, "unique_id", company) or "") or None

        if not company_uid:
            raise PermissionDenied("Company user required")

        return queryset.filter(company_unique_id=company_uid)

    def get_queryset(self):
        queryset = self._scoped_base_queryset()
        params = self.request.query_params

        # Superadmin-only cross-company filters. For a company user the base
        # queryset is already pinned, so a company_id param cannot widen it.
        company_id = params.get("company_unique_id") or params.get("company_id")
        if company_id and is_platform_super_admin(self.request.user):
            queryset = queryset.filter(company_unique_id=company_id)

        project_id = params.get("project_unique_id") or params.get("project_id")
        if project_id:
            # "none" is the frontend sentinel for company-wide rows that
            # belong to no project, matching CompanyScopedViewSet.
            if project_id == "none":
                queryset = queryset.filter(project_unique_id__isnull=True)
            else:
                queryset = queryset.filter(project_unique_id=project_id)

        module_name = params.get("module_name")
        if module_name:
            queryset = queryset.filter(module_name=module_name)

        method = params.get("method")
        if method:
            queryset = queryset.filter(method=method.upper())

        created_by = params.get("createdBy")
        if created_by:
            queryset = queryset.filter(createdBy=created_by)

        created_by_id = params.get("created_by_id")
        if created_by_id:
            queryset = queryset.filter(created_by_id=created_by_id)

        date_from = params.get("date_from")
        if date_from:
            queryset = queryset.filter(createdAt__date__gte=date_from)

        date_to = params.get("date_to")
        if date_to:
            queryset = queryset.filter(createdAt__date__lte=date_to)

        return queryset

    @action(detail=False, methods=["get"], url_path="filter-options")
    def filter_options(self, request):
        """
        Distinct values for the list page's dropdowns, drawn from the same
        scoped queryset so a company user is never offered another
        company's projects.
        """
        queryset = self._scoped_base_queryset()

        # Narrow the project list to the selected company, so picking a
        # company never leaves unrelated projects in the next dropdown.
        # Companies/modules/users stay drawn from the unnarrowed set.
        company_id = (
            request.query_params.get("company_unique_id")
            or request.query_params.get("company_id")
        )

        # The model's Meta.ordering ("-createdAt") is injected into the
        # SELECT by Django, which makes DISTINCT operate on
        # (value, createdAt) pairs and returns the same value once per row.
        # order_by() clears that ordering so DISTINCT applies to the column
        # actually being selected.
        unordered = queryset.order_by()

        def distinct_pairs(id_field, name_field, source=None):
            rows = (
                (source if source is not None else unordered)
                .exclude(**{f"{id_field}__isnull": True})
                .exclude(**{id_field: ""})
                .values_list(id_field, name_field)
                .distinct()
            )
            # A single id can still appear twice if its denormalized name
            # snapshot changed between writes (e.g. the company was
            # renamed). Keep the first and dedupe on the id.
            seen, out = set(), []
            for uid, name in rows:
                if uid in seen:
                    continue
                seen.add(uid)
                out.append({"unique_id": uid, "name": name or uid})
            return sorted(out, key=lambda o: (o["name"] or "").lower())

        def distinct_values(field):
            return sorted(
                {v for v in unordered.values_list(field, flat=True).distinct() if v}
            )

        project_source = unordered
        if company_id:
            project_source = unordered.filter(company_unique_id=company_id)

        return Response({
            "companies": distinct_pairs("company_unique_id", "company_name"),
            "projects": distinct_pairs(
                "project_unique_id", "project_name", source=project_source
            ),
            "modules": distinct_values("module_name"),
            "methods": distinct_values("method"),
            "users": distinct_pairs("created_by_id", "created_by_name"),
        })
