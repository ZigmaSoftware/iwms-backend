from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.zone import Zone
from app.models.masters.panchayat import Panchayat
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.stafftemplate import StaffTemplate
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


def generate_routeplan_id():
    return f"RTP-{generate_unique_id()}"


class RoutePlan(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
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
        related_name="route_plans",
        null=True,
        blank=True,
    )

    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="route_plans",
        null=True,
        blank=True,
    )

    staff_template_id = models.ForeignKey(
        StaffTemplate,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="route_plans",
        null=True,
        blank=True,
        db_column="staff_template_id",
    )

    driver_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        to_field="staff_unique_id",
        related_name="driver_route_plans",
        null=True,
        blank=True,
        db_column="driver_id",
    )

    vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="route_plans"
    )

    supervisor_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        to_field="staff_unique_id",
        related_name="route_plans"
    )
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="route_plans",
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="route_plans",
        db_column="project_id",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.display_code or self.unique_id

    # --------------------------------------------------
    # DISPLAY CODE GENERATOR
    # --------------------------------------------------
    def _generate_display_code(self):
        driver_name = "DRV"
        if self.driver_id and self.driver_id.employee_name:
            driver_name = (
                self.driver_id.employee_name[:10]
                .upper()
                .replace(" ", "")
            )

        vehicle_no = "VEH"
        if self.vehicle_id:
            vehicle_no = self.vehicle_id.vehicle_no.upper().replace(" ", "")

        return f"{driver_name}-{vehicle_no}"

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
