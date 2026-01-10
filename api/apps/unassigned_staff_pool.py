from django.db import models
from api.apps.userCreation import User
from api.apps.zone import Zone
from api.apps.ward import Ward
from api.apps.trip_instance import TripInstance


class UnassignedStaffPool(models.Model):
    """
    Holds operators & drivers who are NOT currently assigned to any trip
    within a specific zone/ward.

    Used by system while creating TripInstance to ensure
    no cross-zone staff allocation.
    """

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        ASSIGNED = "ASSIGNED", "Assigned"

    id = models.BigAutoField(primary_key=True)

    operator = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="unassigned_operator_pool",
        db_column="operator_id",
        to_field="unique_id",
        limit_choices_to={
            "staffusertype_id__name": "operator",
            "is_active": True,
            "is_deleted": False,
        }
    )

    driver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="unassigned_driver_pool",
        db_column="driver_id",
        to_field="unique_id",
        limit_choices_to={
            "staffusertype_id__name": "driver",
            "is_active": True,
            "is_deleted": False,
        }
    )

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

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "unassigned_staff_pool"
        verbose_name = "Unassigned Staff Pool"
        verbose_name_plural = "Unassigned Staff Pools"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["operator", "zone", "ward"],
                name="uniq_operator_zone_ward"
            ),
            models.UniqueConstraint(
                fields=["driver", "zone", "ward"],
                name="uniq_driver_zone_ward"
            ),
        ]

    def __str__(self):
        staff = self.operator or self.driver
        return f"{staff.unique_id if staff else 'N/A'} - {self.zone.name}"

    @classmethod
    def refresh_for_trip_instance(cls, trip_instance):
        """
        Keep a live pool of staff not assigned to active trip instances.
        """
        from api.apps.userCreation import User
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
            if staff_template:
                if staff_template.driver_id_id:
                    assigned_ids.add(staff_template.driver_id_id)
                if staff_template.operator_id_id:
                    assigned_ids.add(staff_template.operator_id_id)

        staff_qs = User.objects.filter(
            staffusertype_id__name__in=["driver", "operator"],
            is_active=True,
            is_deleted=False,
        ).select_related("zone_id", "ward_id", "staffusertype_id")

        if trip_instance and trip_instance.zone_id:
            staff_qs = staff_qs.filter(zone_id=trip_instance.zone_id)

        for staff in staff_qs:
            if staff.unique_id in assigned_ids:
                cls.objects.filter(
                    operator_id=staff.unique_id
                ).update(status=cls.Status.ASSIGNED)
                cls.objects.filter(
                    driver_id=staff.unique_id
                ).update(status=cls.Status.ASSIGNED)
                continue

            zone = staff.zone_id or trip_instance.zone
            if not zone:
                continue

            ward = staff.ward_id or Ward.objects.filter(
                zone_id=zone.unique_id
            ).first()
            if not ward:
                continue

            if trip_instance and trip_instance.zone_id != zone.unique_id:
                continue

            payload = {
                "zone": zone,
                "ward": ward,
                "status": cls.Status.AVAILABLE,
                "trip_instance": trip_instance,
            }

            if staff.staffusertype_id and staff.staffusertype_id.name.lower() == "operator":
                cls.objects.update_or_create(
                    operator=staff,
                    zone=zone,
                    ward=ward,
                    defaults=payload,
                )
            elif staff.staffusertype_id and staff.staffusertype_id.name.lower() == "driver":
                cls.objects.update_or_create(
                    driver=staff,
                    zone=zone,
                    ward=ward,
                    defaults=payload,
                )
