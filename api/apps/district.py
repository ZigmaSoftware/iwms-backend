from django.db import models
from .country import Country
from .state import State
from .continent import Continent
from .utils.comfun import generate_unique_id

def generate_district_id():
    return f"DIST{generate_unique_id()}"

class District(models.Model):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_district_id
    )

    country_id = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="districts",
        to_field="unique_id"
    )

    state_id = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name="districts",
        to_field="unique_id"
    )

    continent_id = models.ForeignKey(
        Continent,
        on_delete=models.PROTECT,
        related_name="districts",
        to_field="unique_id"
    )

    name = models.CharField(max_length=100)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        unique_together = ("state_id", "name")   # FIXED

    def __str__(self):
        return f"{self.name} ({self.state_id.name})"
