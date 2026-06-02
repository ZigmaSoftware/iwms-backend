from app.management.commands.seeders.base import BaseSeeder
from app.models.user_creations.unassigned_staff_pool import UnassignedStaffPool
from app.models.user_creations.staffcreation import Staffcreation
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.masters.ward import Ward


class UnassignedStaffPoolSeeder(BaseSeeder):
    name = "unassigned_staff_pool"

    def run(self):
        staff_qs = Staffcreation.objects.filter(
            staffusertype_id__name__in=["driver", "operator"],
            is_active=True,
            is_deleted=False,
        ).select_related("staffusertype_id")

        if not staff_qs.exists():
            self.log("UnassignedStaffPoolSeeder skipped (no staff users).")
            return

        active_assignments = DailyTripAssignment.objects.filter(
            status__in=[
                DailyTripAssignment.STATUS_SCHEDULED,
                DailyTripAssignment.STATUS_IN_PROGRESS,
            ]
        ).select_related("staff_template_id", "ward_id")

        assigned_ids = set()
        latest_assignment_per_zone = {}
        for assignment in active_assignments:
            staff_template = assignment.staff_template_id
            if staff_template and staff_template.driver_id_id:
                assigned_ids.add(staff_template.driver_id_id)
            if staff_template and staff_template.operator_id_id:
                assigned_ids.add(staff_template.operator_id_id)
            zone = getattr(getattr(assignment, "ward_id", None), "zone_id", None)
            if zone:
                latest_assignment_per_zone.setdefault(zone.unique_id, assignment)

        created = 0
        updated = 0

        for staff in staff_qs:
            if staff.staff_unique_id in assigned_ids:
                UnassignedStaffPool.objects.filter(
                    operator_id=staff.staff_unique_id
                ).update(status=UnassignedStaffPool.Status.ASSIGNED)
                UnassignedStaffPool.objects.filter(
                    driver_id=staff.staff_unique_id
                ).update(status=UnassignedStaffPool.Status.ASSIGNED)
                continue

            assignment_for_staff = active_assignments.first()
            zone = getattr(getattr(assignment_for_staff, "ward_id", None), "zone_id", None)
            
            if not zone:
                continue

            ward = Ward.objects.filter(
                zone_id=zone.unique_id,
                is_active=True,
                is_deleted=False
            ).first()
            if not ward:
                continue

            daily_trip_assignment = latest_assignment_per_zone.get(zone.unique_id)
            payload = {
                "zone": zone,
                "ward": ward,
                "status": UnassignedStaffPool.Status.AVAILABLE,
                "daily_trip_assignment": daily_trip_assignment,
                "company_id": getattr(staff, "company_id", None) or getattr(daily_trip_assignment, "company_id", None),
                "project_id": getattr(staff, "project_id", None) or getattr(daily_trip_assignment, "project_id", None),
            }

            if staff.staffusertype_id and staff.staffusertype_id.name.lower() == "operator":
                _, was_created = UnassignedStaffPool.objects.update_or_create(
                    operator=staff,
                    zone=zone,
                    ward=ward,
                    defaults=payload,
                )
            else:
                _, was_created = UnassignedStaffPool.objects.update_or_create(
                    driver=staff,
                    zone=zone,
                    ward=ward,
                    defaults=payload,
                )

            if was_created:
                created += 1
            else:
                updated += 1

        self.log(f"---Unassigned staff pool seeded | Created: {created}, Updated: {updated}---")
