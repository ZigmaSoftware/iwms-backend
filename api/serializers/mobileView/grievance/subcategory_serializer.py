from rest_framework import serializers

from api.apps.sub_category_citizenGrievance import SubCategory
from api.apps.main_category_citizenGrievance import MainCategory
from api.validators.unique_name_validator import unique_name_validator


class FlexibleMainCategoryField(serializers.PrimaryKeyRelatedField):
    """
    Accept either the numeric PK or the exposed `unique_id` for main categories.
    """

    def to_internal_value(self, data):
        queryset = self.get_queryset()

        if isinstance(data, str) and not data.isdigit():
            try:
                return queryset.get(unique_id=data)
            except queryset.model.DoesNotExist:
                self.fail("does_not_exist", pk_value=data)

        return super().to_internal_value(data)


class SubCategorySerializer(serializers.ModelSerializer):
    mainCategory = FlexibleMainCategoryField(
        queryset=MainCategory.objects.filter(is_deleted=False)
    )
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
            "is_deleted",
        ]
        read_only_fields = ["id", "unique_id", "is_deleted"]
        validators = []  # disable DRF unique constraint
        extra_kwargs = {
            "mainCategory": {"required": False},
        }
    def validate(self, attrs):
        return unique_name_validator(
            Model=SubCategory,
            name_field="name",
            scope_fields=["mainCategory"]
        )(self, attrs)
