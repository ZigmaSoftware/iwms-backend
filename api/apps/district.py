from django.db import models
from .country import Country
from .state import State
from .utils.comfun import generate_unique_id


def generate_district_id():
    # Prepend DIST- to the unique ID
    return f"DIST{generate_unique_id()}"

class District(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_district_id
    )
    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name='districts'
    )
    state = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name='districts'
    )
    name = models.CharField(max_length=100)

    #  New field for soft delete flag
    is_deleted = models.BooleanField(default=False)

    # keep your existing status
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "District"
        verbose_name_plural = "Districts"
        ordering = ["name"]

        #  Make district name unique within each state
        unique_together = ("state", "name")

    def __str__(self):
        return f"{self.name} ({self.state.name})"

    def delete(self, *args, **kwargs):
        """
        Soft delete: mark as deleted instead of removing the record.
        """
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])

        # (optional) you can also deactivate related items if needed
        related_cities = getattr(self, "cities", None)
        if related_cities is not None:
            for city in related_cities.all():
                city.is_deleted = True
                city.save(update_fields=["is_deleted"])

        related_zones = getattr(self, "zones", None)
        if related_zones is not None:
            for zone in related_zones.all():
                zone.is_deleted = True
                zone.save(update_fields=["is_deleted"])

        related_wards = getattr(self, "wards", None)
        if related_wards is not None:
            for ward in related_wards.all():
                ward.is_deleted = True
                ward.save(update_fields=["is_deleted"])
