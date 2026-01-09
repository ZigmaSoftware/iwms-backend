from django.db import models
from django.utils import timezone

from api.apps.routeplan import RoutePlan
from api.apps.stafftemplate import StaffTemplate
from api.apps.property import Property
from api.apps.subproperty import SubProperty
from api.apps.utils.comfun import generate_unique_id


def generate_trip_definition_id():
    return f"TRIPDEF-{generate_unique_id()}"


class TripDefinition(models.Model):
    """
    Defines WHEN a trip should exist.
    This is NOT a trip instance.
    """

    class ApprovalStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        default=generate_trip_definition_id,
        editable=False
    )

    routeplan = models.ForeignKey(
        RoutePlan,
        on_delete=models.PROTECT,
        db_column="routeplan_id",
        to_field="unique_id",
        related_name="trip_definitions"
    )

    staff_template = models.ForeignKey(
        StaffTemplate,
        on_delete=models.PROTECT,
        db_column="staff_template_id",
        to_field="unique_id",
        related_name="trip_definitions"
    )

    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        db_column="property_id",
        to_field="unique_id",
        related_name="trip_definitions"
    )

    sub_property = models.ForeignKey(
        SubProperty,
        on_delete=models.PROTECT,
        db_column="sub_property_id",
        to_field="unique_id",
        related_name="trip_definitions"
    )

    trip_trigger_weight_kg = models.PositiveIntegerField()
    max_vehicle_capacity_kg = models.PositiveIntegerField()

    approval_status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "api_trip_definition"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["approval_status"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.unique_id
