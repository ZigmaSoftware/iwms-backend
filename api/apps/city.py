from django.db import models
from .country import Country
from .state import State
from .district import District
from .utils.comfun import generate_unique_id


def generate_city_id():
    return f"CITY{generate_unique_id()}"


class City(models.Model):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_city_id
    )

    country_id = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="cities",
        to_field="unique_id"
    )

    state_id = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name="cities",
        to_field="unique_id"
    )

    district_id = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name="cities",
        to_field="unique_id"
    )

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.state_id.name})"

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])
