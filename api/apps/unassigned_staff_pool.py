from django.db import models
from .utils.tenancy import CompanyProjectMixin
from django.db.models import Q
from api.apps.staffcreation import StaffOfficeDetails
from api.apps.utils.comfun import generate_unique_id
from api.apps.zone import Zone
from api.apps.ward import Ward
from api.apps.trip_instance import TripInstance


def generate_unassigned_staff_pool_id():
    return f"UNASSSTAFFPOOL-{generate_unique_id()}"


class UnassignedStaffPool(CompanyProjectMixin, models.Model):
    """
    Holds operators & drivers who are NOT currently assigned to any trip
    within a specific zone/ward.

    Used by system while creating TripInstance to ensure
    no cross-zone staff allocation.
    """

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        ASSIGNED = "ASSIGNED", "Assigned"

    # -----------------------------
    # SYSTEM IDENTITY
    # -----------------------------
    unique_id = models.CharField(
        max_length=36,
        unique=True,
        default=generate_unassigned_staff_pool_id,
        editable=False
    )

    # -----------------------------
    # STAFF (EXACTLY ONE REQUIRED)
    # -----------------------------
    operator = models.ForeignKey(
        StaffOfficeDetails,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="unassigned_operator_pool",
        db_column="operator_id",
        to_field="staff_unique_id",
        limit_choices_to={
            "staffusertype_id__name": "operator",
            "is_active": True,
            "is_deleted": False,
        }
    )

    driver = models.ForeignKey(
        StaffOfficeDetails,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="unassigned_driver_pool",
        db_column="driver_id",
        to_field="staff_unique_id",
        limit_choices_to={
            "staffusertype_id__name": "driver",
            "is_active": True,
            "is_deleted": False,
        }
    )

    # -----------------------------
    # LOCATION
    # -----------------------------
    zone = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name="unassigned_staff_pool",
        db_column="zone_id",
        to_field="unique_id"
    )

    ward = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        related_name="unassigned_staff_pool",
        db_column="ward_id",
        to_field="unique_id"
    )

    # -----------------------------
    # STATE
    # -----------------------------
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.AVAILABLE
    )

    trip_instance = models.ForeignKey(
        TripInstance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unassigned_staff_pool",
        db_column="trip_instance_id",
        to_field="unique_id",
        help_text="Trip instance that triggered this pool snapshot"
    )

    # -----------------------------
    # AUDIT
    # -----------------------------
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "api_unassigned_staff_pool"
        verbose_name = "Unassigned Staff Pool"
        verbose_name_plural = "Unassigned Staff Pools"
        ordering = ["-created_at"]
        constraints = [
            # Unique per operator + zone + ward
            models.UniqueConstraint(
                fields=["operator", "zone", "ward"],
                condition=Q(operator__isnull=False),
                name="uniq_operator_zone_ward"
            ),
            # Unique per driver + zone + ward
            models.UniqueConstraint(
                fields=["driver", "zone", "ward"],
                condition=Q(driver__isnull=False),
                name="uniq_driver_zone_ward"
            ),
            # Exactly one of operator or driver must be set
            models.CheckConstraint(
                check=(
                    Q(operator__isnull=False, driver__isnull=True) |
                    Q(operator__isnull=True, driver__isnull=False)
                ),
                name="exactly_one_of_operator_or_driver"
            ),
        ]

    def __str__(self):
        staff = self.operator or self.driver
        return f"{staff.staff_unique_id if staff else 'N/A'} - {self.zone}"

    # ---------------------------------------------------
    # POOL REFRESH LOGIC
    # ---------------------------------------------------
    @classmethod
    def refresh_for_trip_instance(cls, trip_instance):
        """
        Keep a live pool of staff not assigned to active trip instances.
        """
        from api.apps.trip_instance import TripInstance
        from api.apps.ward import Ward

        active_instances = TripInstance.objects.filter(
            status__in=[
                TripInstance.Status.WAITING_FOR_LOAD,
                TripInstance.Status.READY,
                TripInstance.Status.IN_PROGRESS,
            ]
        ).select_related("staff_template")

        assigned_ids = set()
        for instance in active_instances:
            staff_template = instance.staff_template
            if not staff_template:
                continue

            if staff_template.driver_id_id:
                assigned_ids.add(staff_template.driver_id_id)

            if staff_template.operator_id_id:
                assigned_ids.add(staff_template.operator_id_id)

        # Note: StaffOfficeDetails doesn't have direct zone_id/ward_id
        # StaffPersonalDetails has contact_mobile and contact_email
        # Location data is expected to come from StaffOfficeDetails.company_id/project_id
        # or from related tables. This method may need adjustment based on actual requirements.
        
        staff_qs = StaffOfficeDetails.objects.filter(
            staffusertype_id__name__in=["driver", "operator"],
            is_active=True,
            is_deleted=False,
        ).select_related("staffusertype_id")

        for staff in staff_qs:
            # Mark assigned
            if staff.staff_unique_id in assigned_ids:
                cls.objects.filter(operator=staff).update(status=cls.Status.ASSIGNED)
                cls.objects.filter(driver=staff).update(status=cls.Status.ASSIGNED)
                continue

            defaults = {
                "status": cls.Status.AVAILABLE,
                "trip_instance": trip_instance,
            }

            zone = getattr(staff, "zone_id", None) or getattr(trip_instance, "zone", None)
            ward = getattr(staff, "ward_id", None)

            if not ward and zone:
                ward = Ward.objects.filter(
                    zone_id=getattr(zone, "unique_id", zone),
                    is_active=True,
                    is_deleted=False,
                ).first()

            if not zone or not ward:
                continue

            if staff.staffusertype_id.name.lower() == "operator":
                cls.objects.update_or_create(
                    operator=staff,
                    zone=zone,
                    ward=ward,
                    defaults=defaults,
                )
            elif staff.staffusertype_id.name.lower() == "driver":
                cls.objects.update_or_create(
                    driver=staff,
                    zone=zone,
                    ward=ward,
                    defaults=defaults,
                )
