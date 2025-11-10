from django.db import models
from django.core.exceptions import ValidationError
from .country import Country
from .state import State
from .district import District
from .city import City
from .utils.comfun import generate_unique_id


def generate_zone_id():
    # Create readable prefixed ID, e.g., ZONE20251028001
    return f"ZONE{generate_unique_id()}"


class Zone(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_zone_id
    )

    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name='zones'
    )
    state = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name='zones'
    )
    district = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name='zones',
        blank=True,
        null=True
    )
    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name='zones',
        blank=True,
        null=True
    )
    name = models.CharField(max_length=100)

    is_deleted = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Zone"
        verbose_name_plural = "Zones"
        ordering = ["name"]
        #  Removed unique_together since we handle it in clean()

    def __str__(self):
        return f"{self.name} ({self.city.name if self.city else self.state.name})"

    

    def save(self, *args, **kwargs):
        # Run clean() before saving
       
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Soft delete this Zone and related Wards."""
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])

        related_wards = getattr(self, "wards", None)
        if related_wards is not None:
            for ward in related_wards.all():
                ward.is_deleted = True
                ward.is_active = False
                ward.save(update_fields=["is_deleted", "is_active"])
