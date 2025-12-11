from rest_framework import viewsets, status
from rest_framework.response import Response

from api.apps.sub_category_citizenGrievance import SubCategory
from api.serializers.mobileView.grievance.subcategory_serializer import SubCategorySerializer


class SubCategoryViewSet(viewsets.ModelViewSet):
    queryset = SubCategory.objects.filter(is_deleted=False)
    serializer_class = SubCategorySerializer
    lookup_field = "unique_id"

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.deleted()
        return Response({"message": "Sub-category deleted"}, status=status.HTTP_200_OK)
