from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_vehicle_substitution_id():
    return f"VSUB-{generate_unique_id()}"


class TripPlanVehicleSubstitution(BaseMaster):
    """A trip plan temporarily runs on another vehicle while its own vehicle
    is under breakdown — the vehicle counterpart of AlternativeStaffTemplate.

    Daily trip generation uses `replacement_vehicle_id` (with the plan's own
    crew) only while `original_vehicle_id` is under breakdown; it ends when
    that vehicle is back in service or the plan's vehicle is changed. See
    app/services/vehicle_substitution.py.
    """

    STATUS_ACTIVE = "ACTIVE"
    STATUS_ENDED = "ENDED"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_ENDED, "Ended"),
    ]

    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        default=generate_vehicle_substitution_id,
        editable=False,
    )

    company_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    project_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)

    trip_plan_id = models.CharField(max_length=30, db_index=True)
    original_vehicle_id = models.CharField(max_length=40, db_index=True)
    replacement_vehicle_id = models.CharField(max_length=40, db_index=True)
    # The breakdown that started it; null when added from the trip plan screen.
    vehicle_breakdown_id = models.CharField(max_length=50, null=True, blank=True)

    from_date = models.DateField()
    # Null = until the original vehicle is repaired.
    to_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )
    ended_at = models.DateTimeField(null=True, blank=True)
    end_reason = models.CharField(max_length=200, null=True, blank=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("trip_plan_vehicle_substitution_list",)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["trip_plan_id", "status"]),
        ]

    def __str__(self):
        return self.unique_id
