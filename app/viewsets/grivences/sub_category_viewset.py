from rest_framework import viewsets, status
from rest_framework.response import Response
from app.viewsets.superadminmasters.tenant_viewset import TenantModelViewSet

from app.models.grivences.sub_category_citizenGrievance import SubCategory
from app.serializers.grivences.subcategory_serializer import SubCategorySerializer


class SubCategoryViewSet(TenantModelViewSet):
    queryset = SubCategory.objects.filter(is_deleted=False)
    serializer_class = SubCategorySerializer
    lookup_field = "unique_id"

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({"message": "Sub-category deleted"}, status=status.HTTP_200_OK)
