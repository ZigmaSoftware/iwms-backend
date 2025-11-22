from rest_framework import serializers
from api.apps.main_category_citizenGrievance import MainCategory

class MainCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MainCategory
        fields = [
            "id",
            "unique_id",
            "name",
            "is_active",
            "is_delete",
        ]
        read_only_fields = [
            "id",
            "unique_id",
            "is_active",
            "is_delete",
        ]
