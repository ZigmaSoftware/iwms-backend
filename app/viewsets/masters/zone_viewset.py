from rest_framework import viewsets
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.masters.zone import Zone
from app.serializers.masters.zone_serializer import ZoneSerializer


# class ZoneViewSet(CompanyScopedViewSet):
#     serializer_class = ZoneSerializer
#     lookup_field = "unique_id"

#     def get_queryset(self):
#         qs = (
#             Zone.objects
#             .filter(is_deleted=False)
#             .select_related(
#                 "continent_id",
#                 "country_id",
#                 "state_id",
#                 "district_id",
#                 "city_id",
#             )
#         )

#         params = self.request.query_params

#         filter_map = {
#             "continent": "continent_id__unique_id",
#             "country": "country_id__unique_id",
#             "state": "state_id__unique_id",
#             "district": "district_id__unique_id",
#             "city": "city_id__unique_id",
#         }

#         for param, field in filter_map.items():
#             value = params.get(param)
#             if value:
#                 qs = qs.filter(**{field: value})

#         return qs

#     def perform_destroy(self, instance):
#         instance.delete()  # soft delete





from rest_framework.viewsets import ModelViewSet
from app.models.masters.zone import Zone
from app.serializers.masters.zone_serializer import ZoneSerializer
from app.utils.audit_mixin import AuditViewSetMixin


class ZoneViewSet(AuditViewSetMixin,CompanyScopedViewSet):
    queryset = Zone.objects.filter(is_deleted=False)
    serializer_class = ZoneSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT ="zone"


    def get_queryset(self):
        queryset = Zone.objects.filter(is_deleted=False)

        company_uid = self.request.query_params.get("company_id")
        project_uid = self.request.query_params.get("project_id")

        if company_uid:
            queryset = queryset.filter(company_id__unique_id=company_uid)

        if project_uid:
            queryset = queryset.filter(project_id__unique_id=project_uid)

        district_uid = self.request.query_params.get("district") or self.request.query_params.get("district_id")
        city_uid = self.request.query_params.get("city") or self.request.query_params.get("city_id")
        state_uid = self.request.query_params.get("state") or self.request.query_params.get("state_id")

        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)

        if city_uid:
            queryset = queryset.filter(city_id__unique_id=city_uid)

        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
