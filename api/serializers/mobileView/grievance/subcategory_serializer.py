from rest_framework import serializers
from api.apps.sub_category_citizenGrievance import SubCategory


class SubCategorySerializer(serializers.ModelSerializer):
    mainCategory_name = serializers.CharField(source="mainCategory.name", read_only=True)

    class Meta:
        model = SubCategory
        fields = [
            "id",
            "unique_id",
            "name",
            "mainCategory",
            "mainCategory_name",
            "is_active",
            "is_delete",
        ]
        read_only_fields = ["id", "unique_id", "is_delete"]
