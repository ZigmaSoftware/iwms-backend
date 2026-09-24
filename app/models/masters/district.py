from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_district_id():
    return f"DIST-{generate_unique_id()}"


class District(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_district_id
    )

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    country_id = models.CharField(max_length=30, null=True, blank=True)
    state_id = models.CharField(max_length=30, null=True, blank=True)
    continent_id = models.CharField(max_length=30, null=True, blank=True)

    name = models.CharField(max_length=100)

    CASCADE_SOFT_DELETE = (
        "cities",
        "zone_set",
        "panchayat",
        "block_panchayat_unions",
        "district_leader_logins",
        "bin",
        "cp",
        "trip_plans",
        "address_change_requests",
        "complaint_routing_rules",
        "complaint_tickets",
        "customer_creation",
        "users_district",
        "userscreenpermissions",
        "staff_district",
    )
    CACHE_SCOPES = ("district_list", "district_detail")

    class Meta:
        ordering = ["name"]
        unique_together = ("state_id", "name")

    def __str__(self):
        from app.models.common_masters.state import State
        state_name = State.objects.filter(unique_id=self.state_id).values_list("name", flat=True).first()
        return f"{self.name} ({state_name})"

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
    def continent(self):
        from app.models.common_masters.continent import Continent
        if self.continent_id:
            return Continent.objects.filter(unique_id=self.continent_id).first()
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
    def cities(self):
        from app.models.masters.city import City
        return City.objects.filter(district_id=self.unique_id)

    @property
    def zones(self):
        from app.models.masters.zone import Zone
        return Zone.objects.filter(district_id=self.unique_id)

    @property
    def panchayats(self):
        from app.models.masters.panchayat import Panchayat
        return Panchayat.objects.filter(district_id=self.unique_id)

    @property
    def block_panchayat_unions(self):
        from app.models.masters.block_panchayat_union import BlockPanchayatUnion
        return BlockPanchayatUnion.objects.filter(district_id=self.unique_id)