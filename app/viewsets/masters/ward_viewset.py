# from rest_framework import viewsets
# from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
# from app.models.masters.ward import Ward
# from app.serializers.masters.ward_serializer import WardSerializer


# class WardViewSet(CompanyScopedViewSet):
#     serializer_class = WardSerializer
#     lookup_field = "unique_id"

#     def get_queryset(self):
#         qs = (
#             Ward.objects
#             .filter(is_deleted=False)
#             .select_related(
#                 "continent_id",
#                 "country_id",
#                 "state_id",
#                 "district_id",
#                 "city_id",
#                 "zone_id",
#             )
#         )

#         params = self.request.query_params

#         filter_map = {
#             "continent": "continent_id__unique_id",
#             "country": "country_id__unique_id",
#             "state": "state_id__unique_id",
#             "district": "district_id__unique_id",
#             "city": "city_id__unique_id",
#             "zone": "zone_id__unique_id",
#         }

#         for param, field in filter_map.items():
#             value = params.get(param)
#             if value:
#                 qs = qs.filter(**{field: value})

#         is_active = params.get("is_active")
#         if is_active is not None:
#             is_active = is_active.lower()
#             if is_active in ("1", "true", "yes"):
#                 qs = qs.filter(is_active=True)
#             elif is_active in ("0", "false", "no"):
#                 qs = qs.filter(is_active=False)

#         return qs

#     def perform_destroy(self, instance):
#         instance.delete()  # soft delete



from rest_framework.viewsets import ModelViewSet
from app.models.masters.ward import Ward
from app.serializers.masters.ward_serializer import WardSerializer
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.audit_mixin import AuditViewSetMixin


class WardViewSet(AuditViewSetMixin,CompanyScopedViewSet):
    queryset = Ward.objects.filter(is_deleted=False)
    serializer_class = WardSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT ="ward"

    def get_queryset(self):
        queryset = Ward.objects.filter(is_deleted=False)

        company_uid = self.request.query_params.get("company_id")
        project_uid = self.request.query_params.get("project_id")

        if company_uid:
            queryset = queryset.filter(company_id__unique_id=company_uid)

        if project_uid:
            queryset = queryset.filter(project_id__unique_id=project_uid)

        zone_uid = self.request.query_params.get("zone") or self.request.query_params.get("zone_id")
        district_uid = self.request.query_params.get("district") or self.request.query_params.get("district_id")
        city_uid = self.request.query_params.get("city") or self.request.query_params.get("city_id")
        state_uid = self.request.query_params.get("state") or self.request.query_params.get("state_id")

        if zone_uid:
            queryset = queryset.filter(zone_id__unique_id=zone_uid)

        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)

        if city_uid:
            queryset = queryset.filter(city_id__unique_id=city_uid)

        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
