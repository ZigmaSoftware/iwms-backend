from rest_framework import viewsets, status
from rest_framework.response import Response

from api.apps.main_category_citizenGrievance import MainCategory
from api.serializers.mobileView.grievance.maincategory_serializer import MainCategorySerializer


class MainCategoryViewSet(viewsets.ModelViewSet):
    queryset = MainCategory.objects.filter(is_delete=False).order_by("id")
    serializer_class = MainCategorySerializer
    lookup_field = "unique_id"

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_delete = True
        instance.is_active = False
        instance.save(update_fields=["is_delete", "is_active"])
        return Response({"message": "Main category deleted"}, status=status.HTTP_200_OK)
