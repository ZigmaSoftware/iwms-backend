from django.db import models
from api.apps.utils.comfun import generate_unique_id
from api.apps.city import City
from api.apps.district import District
from api.apps.zone import Zone
from api.apps.vehicleCreation import VehicleCreation
from api.apps.userCreation import User


def generate_routeplan_id():
    return f"RTP-{generate_unique_id()}"


class RoutePlan(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_routeplan_id,
        editable=False
    )

    display_code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        editable=False
    )

    district_id = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="route_plans"
    )

    city_id = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="route_plans"
    )

    zone_id = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="route_plans"
    )

    vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="route_plans"
    )

    supervisor_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="route_plans"
    )

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "api_route_plan"
        ordering = ["-created_at"]

    def __str__(self):
        return self.display_code or self.unique_id

    # --------------------------------------------------
    # DISPLAY CODE GENERATOR
    # --------------------------------------------------
    def _generate_display_code(self):
        supervisor_name = "SUP"
        if self.supervisor_id and self.supervisor_id.staff_id:
            supervisor_name = (
                self.supervisor_id.staff_id.employee_name[:10]
                .upper()
                .replace(" ", "")
            )

        vehicle_no = "VEH"
        if self.vehicle_id:
            vehicle_no = self.vehicle_id.vehicle_no.upper().replace(" ", "")

        return f"{supervisor_name}-{vehicle_no}"

    # --------------------------------------------------
    # AUTO SET DISPLAY CODE
    # --------------------------------------------------
    def save(self, *args, **kwargs):
        if not self.display_code:
            base_code = self._generate_display_code()
            code = base_code
            counter = 1

            while RoutePlan.objects.filter(display_code=code).exists():
                code = f"{base_code}-{counter}"
                counter += 1

            self.display_code = code

        super().save(*args, **kwargs)
