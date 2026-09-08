from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.common_masters.continent import Continent
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.validators.unique_name_validator import unique_name_validator

class CitySerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
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
    district_id = NameOrUniqueIdField(
        queryset=District.objects.filter(is_deleted=False),
        name_field="name",
        scope_fields=["state_id", "country_id"],
    )
    company_id = NameOrUniqueIdField(
        queryset=Company.objects.filter(is_deleted=False),
        name_field="name",
    )
    project_id = NameOrUniqueIdField(
        queryset=Project.objects.filter(is_deleted=False),
        name_field="name",
        scope_fields=["company_id"],
    )
    continent_name = serializers.CharField(source="continent_id.name", read_only=True)
    country_name   = serializers.CharField(source="country_id.name", read_only=True)
    state_name     = serializers.CharField(source="state_id.name", read_only=True)
    district_name  = serializers.CharField(source="district_id.name", read_only=True)
    company_name   = serializers.CharField(source="company_id.name", read_only=True)
    project_name   = serializers.CharField(source="project_id.name", read_only=True)
    # UUID read fields — separate names so FK write fields are not clobbered
    continent_unique_id = serializers.CharField(source="continent_id.unique_id", read_only=True)
    country_unique_id   = serializers.CharField(source="country_id.unique_id", read_only=True)
    state_unique_id     = serializers.CharField(source="state_id.unique_id", read_only=True)
    district_unique_id  = serializers.CharField(source="district_id.unique_id", read_only=True)
    

    class Meta:
        model = City
        fields = "__all__"
        read_only_fields = ["unique_id"]    
        validators = []

    def validate(self, attrs):
        return unique_name_validator(
            Model=City,
            scope_fields=["continent_id", "country_id", "state_id", "district_id"]
        )(self, attrs)
