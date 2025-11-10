from django.db import models
from .country import Country
from .state import State
from .district import District
from .utils.comfun import generate_unique_id


def generate_city_id():
    # Create readable prefixed ID, e.g., CITY20251028001
    return f"CITY{generate_unique_id()}"


class City(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_city_id
    )

    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name='cities'
    )
    state = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name='cities'
    )
    district = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name='cities',
        blank=True,
        null=True
    )
    name = models.CharField(max_length=100)

    is_deleted = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "City"
        verbose_name_plural = "Cities"
        ordering = ["name"]
        # Unique constraint handled in validation instead of DB level
        # unique_together = ("state", "name")

    def __str__(self):
        location = f"{self.state.name}"
        if self.district:
            location = f"{self.state.name}, {self.district.name}"
        return f"{self.name} ({location})"

    def save(self, *args, **kwargs):
        # Optional: self.full_clean() before save() if you want validation enforcement
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Soft delete this City and related Zones and Wards.
        """
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])

        # Soft delete related Zones
        related_zones = getattr(self, "zones", None)
        if related_zones is not None:
            for zone in related_zones.all():
                zone.is_deleted = True
                zone.is_active = False
                zone.save(update_fields=["is_deleted", "is_active"])

        # Soft delete related Wards
        related_wards = getattr(self, "wards", None)
        if related_wards is not None:
            for ward in related_wards.all():
                ward.is_deleted = True
                ward.is_active = False
                ward.save(update_fields=["is_deleted", "is_active"])
