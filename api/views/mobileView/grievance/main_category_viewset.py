from rest_framework import viewsets
from api.apps.main_category_citizenGrievance import MainCategory
from api.serializers.mobileView.grievance.maincategory_serializer import MainCategorySerializer


class MainCategoryViewSet(viewsets.ModelViewSet):
    queryset = MainCategory.objects.filter(is_delete=True)
    serializer_class = MainCategorySerializer
