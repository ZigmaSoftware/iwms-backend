from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.common_masters.country import Country
from app.models.common_masters.continent import Continent
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.validators.unique_name_validator import unique_name_validator

class CountrySerializer(serializers.ModelSerializer):
    # Accepts/returns the continent's name (e.g. "Asia") instead of its
    # opaque unique_id, so Excel upload/download and the API all speak names.
    continent_id = NameOrUniqueIdField(
        queryset=Continent.objects.filter(is_deleted=False),
        name_field="name",
    )
    continent_name = serializers.CharField(
        source="continent_id.name", read_only=True
    )
    continent_unique_id = serializers.CharField(source="continent_id.unique_id", read_only=True)

    class Meta:
        model = Country
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def validate(self, attrs):
        return unique_name_validator(
            Model=Country,
            scope_fields=["continent_id"]
        )(self, attrs)
