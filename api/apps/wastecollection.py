from django.db import models
from .customercreation import CustomerCreation
from .country import Country
from .state import State
from .district import District
from .city import City
from .zone import Zone
from .ward import Ward
from .property import Property
from .subproperty import SubProperty
from .utils.comfun import generate_unique_id


def generate_wastecollection_id():
    """Generate readable prefixed ID, e.g., WASTE-20251028001"""
    return f"WASTE-{generate_unique_id()}"

class WasteCollection(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_wastecollection_id
    )

    #  Link one customer – all details fetched via relation
    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.PROTECT,
        related_name="waste_collections"
    )

    #  Waste details
    wet_waste = models.FloatField(default=0.0)
    dry_waste = models.FloatField(default=0.0)
    mixed_waste = models.FloatField(default=0.0)
    total_quantity = models.FloatField(default=0.0)

    # Optional: collection timestamp
    collection_date = models.DateField(auto_now_add=True)
    collection_time = models.TimeField(auto_now_add=True)

    #  Record status
    is_deleted = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Waste Collection"
        verbose_name_plural = "Waste Collections"
        ordering = ["-collection_date", "-collection_time"]

    def __str__(self):
        """Readable entry with linked customer and location."""
        customer_name = self.customer.customer_name if self.customer else "Unknown"
        ward = self.customer.ward.ward_name if self.customer and self.customer.ward else ""
        zone = self.customer.zone.zone_name if self.customer and self.customer.zone else ""
        city = self.customer.city.city_name if self.customer and self.customer.city else ""
        return f"{customer_name} - {ward or zone or city}"

    def save(self, *args, **kwargs):
        """Auto-calculate total before save."""
        self.total_quantity = (
            (self.wet_waste or 0)
            + (self.dry_waste or 0)
            + (self.mixed_waste or 0)
        )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Soft delete this record."""
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
