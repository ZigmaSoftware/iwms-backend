from django.db import models
from .country import Country
  # ideally rename to StateType (class names are PascalCase)
from .utils.comfun import generate_unique_id

def generate_state_id():
    # Prepend STATE- to the unique ID
    return f"STATE-{generate_unique_id()}"

class State(models.Model):
    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name='states'
    )
    
    name = models.CharField(max_length=100)
    label = models.CharField(max_length=20, blank=True, null=True)

    # New soft delete flag
    is_deleted = models.BooleanField(default=False)

    # Keep is_active separately (for enable/disable toggling)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "State"
        verbose_name_plural = "States"
        ordering = ["name"]

        # Ensure each state name is unique within a country
        unique_together = ("country", "name")

    def __str__(self):
        return f"{self.name} ({self.country.name})".strip()
    
    def delete(self, *args, **kwargs):
        """
        Soft delete: mark this State (and related items) as deleted.
        """
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])

        # Soft delete related districts
        related_districts = getattr(self, "districts", None)
        if related_districts is not None:
            for district in related_districts.all():
                district.is_deleted = True
                district.save(update_fields=["is_deleted"])

        # Soft delete related cities
        related_cities = getattr(self, "cities", None)
        if related_cities is not None:
            for city in related_cities.all():
                city.is_deleted = True
                city.save(update_fields=["is_deleted"])

        # Soft delete related zones
        related_zones = getattr(self, "zones", None)
        if related_zones is not None:
            for zone in related_zones.all():
                zone.is_deleted = True
                zone.save(update_fields=["is_deleted"])

        # Soft delete related wards
        related_wards = getattr(self, "wards", None)
        if related_wards is not None:
            for ward in related_wards.all():
                ward.is_deleted = True
                ward.save(update_fields=["is_deleted"])

