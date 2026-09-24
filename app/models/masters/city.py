from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_city_id():
    return f"CITY-{generate_unique_id()}"


class City(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_city_id
    )

    continent_id = models.CharField(max_length=30, null=True, blank=True)
    country_id = models.CharField(max_length=30, null=True, blank=True)
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    CASCADE_SOFT_DELETE = (
        "zone_set",
        "panchayat",
        "ward_set",
        "bin",
        "customer_creation",
        "users_city",
        "userscreenpermissions",
        "staff_city",
    )
    CACHE_SCOPES = ("city_list", "city_detail")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        from app.models.common_masters.state import State
        state_name = State.objects.filter(unique_id=self.state_id).values_list("name", flat=True).first()
        return f"{self.name} ({state_name})"

    @property
    def continent(self):
        from app.models.common_masters.continent import Continent
        if self.continent_id:
            return Continent.objects.filter(unique_id=self.continent_id).first()
        return None

    @property
    def country(self):
        from app.models.common_masters.country import Country
        if self.country_id:
            return Country.objects.filter(unique_id=self.country_id).first()
        return None

    @property
    def state(self):
        from app.models.common_masters.state import State
        if self.state_id:
            return State.objects.filter(unique_id=self.state_id).first()
        return None

    @property
    def district(self):
        from app.models.masters.district import District
        if self.district_id:
            return District.objects.filter(unique_id=self.district_id).first()
        return None

    @property
    def company(self):
        from app.models.superadmin_masters.company import Company
        if self.company_id:
            return Company.objects.filter(unique_id=self.company_id).first()
        return None

    @property
    def project(self):
        from app.models.superadmin_masters.project import Project
        if self.project_id:
            return Project.objects.filter(unique_id=self.project_id).first()
        return None

    @property
    def zones(self):
        from app.models.masters.zone import Zone
        return Zone.objects.filter(city_id=self.unique_id)

    @property
    def panchayats(self):
        from app.models.masters.panchayat import Panchayat
        return Panchayat.objects.filter(city_id=self.unique_id)

    @property
    def wards(self):
        from app.models.masters.ward import Ward
        return Ward.objects.filter(city_id=self.unique_id)