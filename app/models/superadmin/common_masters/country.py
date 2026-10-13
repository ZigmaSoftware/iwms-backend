from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_country_id():
    return f"COUNTRY-{generate_unique_id()}"


class Country(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_country_id
    )

    continent_id = models.CharField(max_length=30, null=True, blank=True)

    name = models.CharField(max_length=100)
    currency = models.CharField(max_length=20, blank=True, null=True)
    mob_code = models.CharField(max_length=5, blank=True, null=True)

    CASCADE_SOFT_DELETE = ("states", "customer_creation")
    CACHE_SCOPES = ("country_list", "country_detail")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def continent(self):
        from app.models.superadmin.common_masters.continent import Continent
        if self.continent_id:
            return Continent.objects.filter(unique_id=self.continent_id).first()
        return None

    @property
    def states(self):
        from app.models.superadmin.common_masters.state import State
        return State.objects.filter(country_id=self.unique_id)