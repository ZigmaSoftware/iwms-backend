from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin

from app.models.core_modules.complaint_management.sub_category_citizenGrievance import SubCategory
from app.models.core_modules.complaint_management.main_category_citizenGrievance import MainCategory
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.validators.unique_name_validator import unique_name_validator


class SubCategorySerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    mainCategory = NameOrUniqueIdField(
        name_field="main_categoryName",
        queryset=MainCategory.objects.filter(is_deleted=False)
    )
    mainCategory_name = serializers.SerializerMethodField()

    def get_mainCategory_name(self, obj):
        return getattr(obj.mainCategory_obj, "main_categoryName", None)

    class Meta:
        model = SubCategory
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "name",
            "mainCategory",
            "mainCategory_name",
            "is_active",
            "is_deleted",
        ]
        read_only_fields = ["unique_id", "is_deleted"]
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
