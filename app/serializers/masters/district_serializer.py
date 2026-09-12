from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.masters.district import District
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.common_masters.continent import Continent
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.validators.unique_name_validator import unique_name_validator

class DistrictSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    # Excel/API now take "India", "Tamil Nadu" etc. instead of the raw
    # unique_id — state lookup is scoped to the given country so identically
    # named states in different countries don't collide.
    continent_id = NameOrUniqueIdField(
        queryset=Continent.objects.filter(is_deleted=False),
        name_field="name",
    )
    country_id = NameOrUniqueIdField(
        queryset=Country.objects.filter(is_deleted=False),
        name_field="name",
        scope_fields=["continent_id"],
    )
    state_id = NameOrUniqueIdField(
        queryset=State.objects.filter(is_deleted=False),
        name_field="name",
        scope_fields=["country_id", "continent_id"],
    )
    # Mirrors CitySerializer: writable so Excel bulk-import (and the POST
    # metadata that drives its Download Template) can resolve these by name
    # instead of only exposing them as TenancyReadSerializerMixin's
    # read-only fields. Unlike City, District's company_id/project_id are
    # nullable on the model (a district can be global/unscoped), so these
    # stay optional rather than required.
    company_id = NameOrUniqueIdField(
        queryset=Company.objects.filter(is_deleted=False),
        name_field="name",
        required=False,
        allow_null=True,
    )
    project_id = NameOrUniqueIdField(
        queryset=Project.objects.filter(is_deleted=False),
        name_field="name",
        scope_fields=["company_id"],
        required=False,
        allow_null=True,
    )
    continent_name    = serializers.CharField(source="continent_id.name", read_only=True)
    country_name      = serializers.CharField(source="country_id.name", read_only=True)
    state_name        = serializers.CharField(source="state_id.name", read_only=True)
    # UUID read fields — separate names so FK write fields are not clobbered
    state_unique_id   = serializers.CharField(source="state_id.unique_id", read_only=True)
    country_unique_id = serializers.CharField(source="country_id.unique_id", read_only=True)
    continent_unique_id = serializers.CharField(source="continent_id.unique_id", read_only=True)

    class Meta:
        model = District
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def validate(self, attrs):
        return unique_name_validator(
            Model=District,
            scope_fields=["continent_id", "country_id", "state_id"]
        )(self, attrs)
