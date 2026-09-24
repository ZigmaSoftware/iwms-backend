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
    continent_name = serializers.SerializerMethodField()
    country_name = serializers.SerializerMethodField()
    state_name = serializers.SerializerMethodField()
    district_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()
    # UUID read fields — separate names so FK write fields are not clobbered
    continent_unique_id = serializers.SerializerMethodField()
    country_unique_id = serializers.SerializerMethodField()
    state_unique_id = serializers.SerializerMethodField()
    district_unique_id = serializers.SerializerMethodField()
    

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

    def get_continent_name(self, obj):
        item = Continent.objects.filter(unique_id=obj.continent_id).first()
        return item.name if item else None

    def get_country_name(self, obj):
        item = Country.objects.filter(unique_id=obj.country_id).first()
        return item.name if item else None

    def get_state_name(self, obj):
        item = State.objects.filter(unique_id=obj.state_id).first()
        return item.name if item else None

    def get_district_name(self, obj):
        item = District.objects.filter(unique_id=obj.district_id).first()
        return item.name if item else None

    def get_company_name(self, obj):
        item = Company.objects.filter(unique_id=obj.company_id).first()
        return item.name if item else None

    def get_project_name(self, obj):
        item = Project.objects.filter(unique_id=obj.project_id).first()
        return item.name if item else None

    def get_continent_unique_id(self, obj):
        return obj.continent_id

    def get_country_unique_id(self, obj):
        return obj.country_id

    def get_state_unique_id(self, obj):
        return obj.state_id

    def get_district_unique_id(self, obj):
        return obj.district_id
