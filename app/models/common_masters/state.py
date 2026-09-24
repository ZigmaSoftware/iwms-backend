from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_state_id():
    return f"STATE-{generate_unique_id()}"


class State(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_state_id
    )

    country_id = models.CharField(max_length=30, null=True, blank=True)
    continent_id = models.CharField(max_length=30, null=True, blank=True)

    name = models.CharField(max_length=100)
    label = models.CharField(max_length=20, blank=True, null=True)

    CASCADE_SOFT_DELETE = (
        "districts",
        "customer_creation",
        "complaint_routing_rules",
        "complaint_tickets",
        "address_change_requests",
        "userscreenpermissions",
    )
    CACHE_SCOPES = ("state_list", "state_detail")

    class Meta:
        ordering = ["name"]
        unique_together = ("country_id", "name")

    def __str__(self):
        from app.models.common_masters.country import Country
        country_name = Country.objects.filter(unique_id=self.country_id).values_list("name", flat=True).first()
        return f"{self.name} ({country_name})"

    @property
    def country(self):
        from app.models.common_masters.country import Country
        if self.country_id:
            return Country.objects.filter(unique_id=self.country_id).first()
        return None

    @property
    def continent(self):
        from app.models.common_masters.continent import Continent
        if self.continent_id:
            return Continent.objects.filter(unique_id=self.continent_id).first()
        return None

    @property
    def districts(self):
        from app.models.masters.district import District
        return District.objects.filter(state_id=self.unique_id)