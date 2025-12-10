from rest_framework import serializers
from api.apps.sub_category_citizenGrievance import SubCategory
from api.validators.unique_name_validator import unique_name_validator


class SubCategorySerializer(serializers.ModelSerializer):
    mainCategory_name = serializers.CharField(
        source="mainCategory.main_categoryName", read_only=True
    )

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
        validators = []  # disable DRF unique constraint
    def validate(self, attrs):
        return unique_name_validator(
            Model=SubCategory,
            name_field="name",
            scope_fields=["mainCategory"]
        )(self, attrs)
