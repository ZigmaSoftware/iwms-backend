from rest_framework import viewsets, status
from rest_framework.response import Response

from api.apps.sub_category_citizenGrievance import SubCategory
from api.serializers.mobileView.grievance.subcategory_serializer import SubCategorySerializer


class SubCategoryViewSet(viewsets.ModelViewSet):
    queryset = SubCategory.objects.filter(is_delete=False)
    serializer_class = SubCategorySerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({"message": "Sub-category deleted"}, status=status.HTTP_200_OK)
