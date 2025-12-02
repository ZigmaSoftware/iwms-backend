from django.db import models
from .country import Country
from .state import State
from .district import District
from .utils.comfun import generate_unique_id


def generate_city_id():
    return f"CITY{generate_unique_id()}"


class City(models.Model):
    city_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_city_id
    )

    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="cities", to_field="country_id")
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name="cities", to_field="state_id")
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="cities",
                                 blank=True, null=True, to_field="district_id")

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
