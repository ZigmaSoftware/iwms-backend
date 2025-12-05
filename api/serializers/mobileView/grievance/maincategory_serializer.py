from rest_framework import serializers
from api.apps.main_category_citizenGrievance import MainCategory
from api.validators.unique_name_validator import unique_name_validator

class MainCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MainCategory
        fields = [
            "id",
            "unique_id",
            "main_categoryName",
            "is_active"
        ]
        read_only_fields = ["unique_id"]
        validators = []  # disable DRF unique constraint

    def validate(self, attrs):
        return unique_name_validator(
            Model=MainCategory,
            name_field="main_categoryName",
        )(self, attrs)