from django.db import models
from .country import Country
from .state import State
from .district import District
from .city import City
from .zone import Zone
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

    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="wards",
        to_field="unique_id"
    )

    state = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name="wards",
        to_field="unique_id"
    )

    district = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name="wards",
        to_field="unique_id"
    )

    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name="wards",
        to_field="unique_id"
    )

    zone = models.ForeignKey(
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
        return f"{self.name} ({self.city.name if self.city else self.state.name})"

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
