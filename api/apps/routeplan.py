from django.db import models
from api.apps.utils.comfun import generate_unique_id


def generate_routeplan_id():
    return f"RTP-{generate_unique_id()}"


class RoutePlan(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_routeplan_id,
        editable=False
    )

    district_id = models.ForeignKey(
        "District",
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="district_id",
        related_name="route_plans"
    )

    city_id = models.ForeignKey(
        "City",
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="city_id",
        related_name="route_plans"
    )

    vehicle_id = models.ForeignKey(
        "VehicleCreation",
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="vehicle_id",
        related_name="route_plans"
    )

    supervisor_id = models.ForeignKey(
        "User",
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="supervisor_id",
        related_name="route_plans"
    )

    status = models.CharField(
        max_length=10,
        choices=(
            ("ACTIVE", "Active"),
            ("INACTIVE", "Inactive"),
        ),
        default="ACTIVE"
    )

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "api_route_plan"
        ordering = ["-created_at"]

    def __str__(self):
        return self.unique_id

    def delete(self, *args, **kwargs):
        """Soft delete"""
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
