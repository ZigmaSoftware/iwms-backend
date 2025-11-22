from rest_framework import serializers
from api.apps.main_category_citizenGrievance import MainCategory
from api.apps.sub_category_citizenGrievance import SubCategory


class SubCategorySerializer(serializers.ModelSerializer):
    mainCategory = serializers.PrimaryKeyRelatedField(
        queryset=MainCategory.objects.filter(is_active=True, is_delete=False)
    )
    mainCategory_name = serializers.CharField(
        source="mainCategory.name", read_only=True
    )

    class Meta:
        model = SubCategory
        fields = [
            "id",
            "unique_id",
            "mainCategory",
            "mainCategory_name",
            "name",
            "currency",
            "mob_code",
            "is_active",
            "is_delete",
        ]
        read_only_fields = ["id", "unique_id", "is_active", "is_delete"]
