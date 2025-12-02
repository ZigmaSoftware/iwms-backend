from django.db import models
from .country import Country
from .state import State
from .utils.comfun import generate_unique_id

def generate_district_id():
    return f"DIST{generate_unique_id()}"


class District(models.Model):
    district_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_district_id
    )

    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="districts",
        to_field="country_id"
    )
    state = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name="districts",
        to_field="state_id"
    )

    name = models.CharField(max_length=100)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        unique_together = ("state", "name")

    def __str__(self):
        return f"{self.name} ({self.state.name})"
