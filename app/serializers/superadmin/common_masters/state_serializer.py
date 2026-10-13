from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.superadmin.common_masters.state import State
from app.models.superadmin.common_masters.country import Country
from app.models.superadmin.common_masters.continent import Continent
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
    continent_name = serializers.SerializerMethodField()
    country_name = serializers.SerializerMethodField()
    continent_unique_id = serializers.SerializerMethodField()
    country_unique_id = serializers.SerializerMethodField()

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

    def get_continent_name(self, obj):
        continent = Continent.objects.filter(unique_id=obj.continent_id).first()
        return continent.name if continent else None

    def get_country_name(self, obj):
        country = Country.objects.filter(unique_id=obj.country_id).first()
        return country.name if country else None

    def get_continent_unique_id(self, obj):
        return obj.continent_id

    def get_country_unique_id(self, obj):
        return obj.country_id
