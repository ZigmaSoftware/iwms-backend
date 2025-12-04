from django.db import models
from .country import Country
from .state import State
from .district import District
from .city import City
from .zone import Zone
from .continent import Continent
from .utils.comfun import generate_unique_id


def generate_ward_id():
    return f"WARD{generate_unique_id()}"


class Ward(models.Model):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_ward_id
    )

    continent_id = models.ForeignKey(
        Continent,
        on_delete=models.PROTECT,
        related_name="wards",
        to_field="unique_id"
    )

    country_id = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="wards",
        to_field="unique_id"
    )

    state_id = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name="wards",
        to_field="unique_id"
    )

    district_id = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name="wards",
        to_field="unique_id"
    )

    city_id = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name="wards",
        to_field="unique_id"
    )

    zone_id = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name="wards",
        to_field="unique_id"
    )

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        city = getattr(self, "city_id", None)
        state = getattr(self, "state_id", None)
        location = city.name if city else (state.name if state else "")
        return f"{self.name} ({location})" if location else self.name

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
