from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.common_masters.state import State
from app.models.common_masters.country import Country
from app.models.common_masters.continent import Continent
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.validators.unique_name_validator import unique_name_validator

class StateSerializer( serializers.ModelSerializer):
    # Accept/return "India" rather than the country's unique_id — scoped to
    # continent when both are given, so identical country names in different
    # continents (shouldn't happen, but mirrors the tenant-scoping pattern
    # used elsewhere) don't collide.
    country_id = NameOrUniqueIdField(
        queryset=Country.objects.filter(is_deleted=False),
        name_field="name",
        scope_fields=["continent_id"],
    )
    continent_id = NameOrUniqueIdField(
        queryset=Continent.objects.filter(is_deleted=False),
        name_field="name",
    )
    continent_name = serializers.CharField(source="continent_id.name", read_only=True)
    country_name = serializers.CharField(source="country_id.name", read_only=True)
    continent_unique_id = serializers.CharField(source="continent_id.unique_id", read_only=True)
    country_unique_id   = serializers.CharField(source="country_id.unique_id", read_only=True)

    class Meta:
        model = State
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def validate(self, attrs):
        return unique_name_validator(
            Model=State,
            scope_fields=["continent_id", "country_id"]
        )(self, attrs)
