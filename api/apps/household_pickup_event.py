from django.db import models
from django.utils import timezone

from api.apps.customercreation import CustomerCreation
from api.apps.zone import Zone
from api.apps.property import Property
from api.apps.subproperty import SubProperty
from api.apps.userCreation import User
from api.apps.vehicleCreation import VehicleCreation


class HouseholdPickupEvent(models.Model):
    """
    Immutable household-level pickup record.
    One row = one pickup event.
    """

    class Source(models.TextChoices):
        HOUSEHOLD_WASTE = "HOUSEHOLD_WASTE", "Household Waste (direct pickup)"
        HOUSEHOLD_BIN = "HOUSEHOLD_BIN", "Household Bin"
        OTHERS = "OTHERS", "Others / Manual"

    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.PROTECT,
        related_name="pickup_events",
        db_column="customer_id",
        to_field="unique_id",
    )

    zone = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name="pickup_events",
        db_column="zone_id",
        to_field="unique_id",
    )

    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="pickup_events",
        db_column="property_id",
        to_field="unique_id",
    )

    sub_property = models.ForeignKey(
        SubProperty,
        on_delete=models.PROTECT,
        related_name="pickup_events",
        db_column="sub_property_id",
        to_field="unique_id",
    )

    pickup_time = models.DateTimeField(default=timezone.now)

    weight_kg = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Measured or estimated weight in KG"
    )

    photo_url = models.ImageField(
        upload_to="uploads/household_pickups/",
        null=True,
        blank=True,
        help_text="Evidence photo (optional)"
    )

    collector_staff = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="collected_pickups",
        db_column="collector_staff_id",
        to_field="unique_id",
        help_text="Operator / collector user"
    )

    vehicle = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        related_name="pickup_events",
        db_column="vehicle_id",
        to_field="unique_id",
    )

    source = models.CharField(
        max_length=30,
        choices=Source.choices,
        help_text="Pickup source type"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "household_pickup_event"
        ordering = ["-pickup_time"]
        indexes = [
            models.Index(fields=["pickup_time"]),
            models.Index(fields=["zone"]),
            models.Index(fields=["collector_staff"]),
            models.Index(fields=["source"]),
        ]

    def __str__(self):
        return f"{self.customer_id} | {self.pickup_time} | {self.source}"
