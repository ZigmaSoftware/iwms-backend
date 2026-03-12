from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.transport_masters.trip import Trip
from decimal import Decimal
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


def generate_weighbridge_id():
    return f"WBC-{generate_unique_id()}"


class WeighbridgeCheck(BaseMaster):

    STATUS_CHOICES = [
        ("Very Good", "Very Good"),
        ("Good", "Good"),
        ("Serious", "Serious"),
        ("Critical", "Critical"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_weighbridge_id,
        editable=False
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        db_column="company_id",
        
    )

    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        db_column="project_id",
        
    )

    trip_id = models.ForeignKey(
        Trip,
        on_delete=models.PROTECT,
        related_name="weighbridge_checks",
        db_column="trip_id"
    )

    weighbridge_weight = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    weight_difference = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        blank=True
    )

    checked_date = models.DateField()
    collected_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # -----------------------------------------
    # BUSINESS LOGIC
    # -----------------------------------------


    @property
    def total_collected_weight(self):
        from django.db.models import Sum

        total = self.trip_id.point_collections.aggregate(
            total=Sum("point_collection_weight")
        )["total"]

        return total or Decimal("0.00")


    def save(self, *args, **kwargs):

        total_collected = self.total_collected_weight

        if total_collected > 0:
            self.weight_difference = self.weighbridge_weight - total_collected

            difference_percent = abs(
                (self.weight_difference / total_collected) * 100
            )

            if difference_percent <= 2:
                self.status = "Very Good"
            elif difference_percent <= 5:
                self.status = "Good"
            elif difference_percent <= 10:
                self.status = "Serious"
            else:
                self.status = "Critical"

        super().save(*args, **kwargs)

        if not self.trip_id.is_completed:
            self.trip_id.is_active = False
            self.trip_id.is_completed = True
            self.trip_id.save(update_fields=["is_completed","is_active"])