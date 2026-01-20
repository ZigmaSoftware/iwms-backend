from django.db import models
from .utils.comfun import generate_unique_id
from .userCreation import User


def generate_supervisor_zone_map_id():
    return f"SUPZONE-{generate_unique_id()}"


class SupervisorZoneMap(models.Model):
    # -----------------------------
    # SYSTEM IDENTITY
    # -----------------------------
    unique_id = models.CharField(
        max_length=36,
        unique=True,
        default=generate_supervisor_zone_map_id,
        editable=False
    )

    # -----------------------------
    # SUPERVISOR & LOCATION
    # -----------------------------
    supervisor_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="zone_assignments",
        to_field="unique_id",
        db_column="supervisor_id"
    )

    district_id = models.ForeignKey(
        "District",
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="district_id"
    )

    city_id = models.ForeignKey(
        "City",
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="city_id"
    )

    # Example: ["ZONExxxx", "ZONEyyyy"]
    zone_ids = models.JSONField(
        help_text="List of zone unique IDs the supervisor is authorized to operate in"
    )

    # -----------------------------
    # STATE
    # -----------------------------
    STATUS_CHOICES = (
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="ACTIVE"
    )

    # -----------------------------
    # AUDIT
    # -----------------------------
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "api_supervisor_zone_map"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["supervisor_id", "status"]),  
            models.Index(fields=["district_id", "city_id"]),
        ]

    def __str__(self):
        return f"{self.supervisor_id} → {self.zone_ids}"
