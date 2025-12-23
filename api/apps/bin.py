from django.db import models
from django.utils import timezone
from .utils.comfun import generate_unique_id
from .ward import Ward


def generate_bin_id():
    return f"BIN-{generate_unique_id()}"


class BinStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    FULL = "full", "Full"
    DAMAGED = "damaged", "Damaged"
    MAINTENANCE = "maintenance", "Maintenance"
    DECOMMISSIONED = "decommissioned", "Decommissioned"


class BinType(models.TextChoices):
    PUBLIC = "public", "Public"
    COMMERCIAL = "commercial", "Commercial"
    RESIDENTIAL = "residential", "Residential"


class WasteType(models.TextChoices):
    ORGANIC = "organic", "Organic"
    PLASTIC = "plastic", "Plastic"
    METAL = "metal", "Metal"
    PAPER = "paper", "Paper"
    MIXED = "mixed", "Mixed"


class Bin(models.Model):
    # ---------- Identity ----------
    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        default=generate_bin_id,
        editable=False,
    )

    # ---------- Relations ----------
    ward = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        related_name="bins",
        to_field="unique_id",
        db_column="ward_id",
    )

    # ---------- Classification ----------
    bin_name = models.CharField(max_length=100)
    bin_type = models.CharField(
        max_length=20,
        choices=BinType.choices,
    )
    waste_type = models.CharField(
        max_length=20,
        choices=WasteType.choices,
    )
    color_code = models.CharField(max_length=20)

    # ---------- Capacity ----------
    capacity_liters = models.PositiveIntegerField()

    # ---------- Geo ----------
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    # ---------- Lifecycle ----------
    installation_date = models.DateField()
    expected_life_years = models.PositiveSmallIntegerField()
    bin_status = models.CharField(
        max_length=20,
        choices=BinStatus.choices,
        default=BinStatus.ACTIVE,
    )

    # ---------- Soft Delete & State ----------
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    # ---------- Audit ----------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["bin_name"]
        indexes = [
            models.Index(fields=["ward"]),
            models.Index(fields=["bin_status"]),
            models.Index(fields=["is_active", "is_deleted"]),
            models.Index(fields=["latitude", "longitude"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(capacity_liters__gt=0),
                name="bin_capacity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.bin_name} ({self.unique_id})"

    # ---------- Soft Delete ----------
    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])

    def hard_delete(self):
        super().delete()
