from django.db import models
from .utils.comfun import generate_unique_id
from .userCreation import User


def generate_supervisor_zone_map_id():
    return f"SUPZONE-{generate_unique_id()}"


class SupervisorZoneMap(models.Model):
    # -----------------------------
    # SYSTEM IDENTITY
    # -----------------------------
    id = models.BigAutoField(primary_key=True)

    unique_id = models.CharField(
        max_length=36,
        unique=True,
        default=generate_supervisor_zone_map_id,
        editable=False
    )

    # -----------------------------
    # SUPERVISOR & LOCATION
    # -----------------------------
    supervisor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="zone_assignments",
        to_field="unique_id",
        db_column="supervisor_id"
    )

    district_id = models.BigIntegerField()
    city_id = models.BigIntegerField()

    # Example: [101, 102, 103]
    zone_ids = models.JSONField(
        help_text="List of zone IDs the supervisor is authorized to operate in"
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
        db_table = "supervisor_zone_map"
        indexes = [
            models.Index(fields=["supervisor", "status"]),
            models.Index(fields=["district_id", "city_id"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.supervisor_id} → {self.zone_ids}"
