from rest_framework import serializers
from api.apps.main_category_citizenGrievance import MainCategory

class MainCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MainCategory
        fields = [
            "id",
            "unique_id",
            "main_categoryName",
            "is_active",
        ]
