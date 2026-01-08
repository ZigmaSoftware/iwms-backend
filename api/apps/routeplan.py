from django.db import models
from api.apps.utils.comfun import generate_unique_id


def generate_routeplan_id():
    return f"RTP{generate_unique_id()}"


class RoutePlan(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_routeplan_id
    )

    # store unique_id values from District and Zone (string primary keys)
    district_id = models.CharField(max_length=30)
    zone_id = models.CharField(max_length=30)
    vehicle_id = models.BigIntegerField()
    supervisor_id = models.BigIntegerField()

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
        ordering = ["id"]

    def __str__(self):
        return self.unique_id

    def delete(self, *args, **kwargs):
        """
        Soft delete – same behavior as SubCategory
        """
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
