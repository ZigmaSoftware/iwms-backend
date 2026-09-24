from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response

from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.serializers.core_modules.schedule_setup.trip_plan_serializer import (
    TripPlanSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.viewsets.superadmin_masters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)
from app.utils.pagination import LimitOffsetWithPage


class TripPlanViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    # Every field above (company_id, staff_template_id, wards, etc.) is now a
    # plain CharField/TextField id column, not a real ForeignKey/M2M, so
    # select_related/prefetch_related can no longer follow them — the
    # serializer resolves each one on demand via its own queries instead.
    queryset = TripPlan.objects.filter(is_deleted=False)

    serializer_class = TripPlanSerializer
    lookup_field = "unique_id"
    swagger_tags = ["Desktop / Operations / Trip Plan"]
    permission_resource = "TripPlan"
    filter_backends = [
        ModelFieldQueryFilter,
        ModelFieldSearchFilter,
        SerializerOrderingFilter,
    ]
    pagination_class = LimitOffsetWithPage
    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "trip-plans"

    def get_queryset(self):
        qs = super().get_queryset()

        if self._is_supervisor_user():
            qs = qs.filter(supervisor_id=self.request.user.staff_unique_id)

        return qs

    @swagger_auto_schema(request_body=TripPlanSerializer)
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(request_body=TripPlanSerializer)
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.daily_trip_assignments.filter(is_deleted=False).exists():
            return Response(
                {"detail": "Trip plans with daily assignments cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)
