from datetime import time

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.staff_creations.staffcreation import Staffcreation
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.staff_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


BASE_TIMES = [
    time(6, 0),  time(6, 30),  time(7, 0),  time(7, 30),  time(8, 0),
    time(8, 30),  time(9, 0),  time(9, 30),  time(10, 0), time(10, 30),
    time(11, 0), time(11, 30), time(12, 0),  time(12, 30), time(13, 0),
]

# Drivers whose trip plans are hand-seeded elsewhere and must NOT receive
# extra auto-generated ward/panchayat plans from this generic seeder.
EXCLUDED_DRIVER_USERNAMES = ["driver_user"]


class TripPlanSeeder(BaseSeeder):
    name = "trip_plan"

    def run(self):
        company = Company.objects.filter(name="IWMS").first()
        project = (
            Project.objects.filter(name=f"{company.name} Main Project").first()
            if company else None
        )
        if not company or not project:
            self.log("TripPlanSeeder skipped (missing company/project).")
            return

        district = District.objects.filter(company_id=company, project_id=project).first()
        city = City.objects.filter(company_id=company, project_id=project).first()
        property_obj = Property.objects.filter(is_deleted=False).first()
        sub_property_obj = SubProperty.objects.filter(is_deleted=False).first()
        supervisor = Staffcreation.objects.filter(is_deleted=False).order_by("created_at").first()

        if not all([district, city, property_obj, sub_property_obj, supervisor]):
            self.log("TripPlanSeeder skipped (missing dependencies).")
            return

        # `driver_user` is the mobile-app demo driver and owns exactly two
        # hand-built trip plans (the Wet/Dry bin rounds seeded by
        # `driver_wet_dry_bin_trips`). This generic seeder cycles every
        # active StaffTemplate across its ward/panchayat plans, which would
        # otherwise hand driver_user extra auto-generated trips
        # (DRIVER-<VEHICLE>-01/-02) on top of those two — so skip any
        # template driven by them.
        staff_templates = list(StaffTemplate.objects.filter(
            is_deleted=False, status="ACTIVE"
        ).exclude(
            driver_id__username__in=EXCLUDED_DRIVER_USERNAMES,
        ).order_by("created_at"))

        vehicles = list(VehicleCreation.objects.filter(
            company_id=company, project_id=project, is_deleted=False
        ).order_by("created_at"))

        if not staff_templates or not vehicles:
            self.log("TripPlanSeeder skipped (no staff templates or vehicles).")
            return

        waste_types = {
            "wet": WasteType.objects.filter(waste_type_name__iexact="Wet Waste", is_deleted=False).first(),
            "dry": WasteType.objects.filter(waste_type_name__iexact="Dry Waste", is_deleted=False).first(),
        }
        fallback_waste = WasteType.objects.filter(is_deleted=False).first()

        def waste_id_list(*items):
            ids = []
            for waste_type in items:
                if waste_type and waste_type.unique_id and waste_type.unique_id not in ids:
                    ids.append(waste_type.unique_id)
            return ids

        common_defaults = dict(
            district_id=district,
            city_id=city,
            supervisor_id=supervisor,
            property_id=property_obj,
            sub_property_id=sub_property_obj,
            trip_trigger_weight_kg=800,
            max_vehicle_capacity_kg=3000,
            approval_status=TripPlan.ApprovalStatus.APPROVED,
            status=TripPlan.Status.ACTIVE,
            is_auto_assign=True,
            repeat_days=[],
        )

        # Approve any already-active plans
        TripPlan.objects.filter(
            company_id=company, project_id=project, status=TripPlan.Status.ACTIVE,
        ).update(approval_status=TripPlan.ApprovalStatus.APPROVED)

        # ------------------------------------------------------------------
        # Ward-based trip plans
        # zone_id is derived from each ward's own zone FK (ward → Zone 1).
        # ------------------------------------------------------------------
        wards = list(Ward.objects.filter(
            company_id=company, project_id=project, is_deleted=False
        ).select_related("zone_id").order_by("ward_name")[:15])

        ward_created = ward_skipped = 0
        for idx, ward in enumerate(wards):
            waste_key = "wet" if idx % 2 == 0 else "dry"
            waste_type = waste_types.get(waste_key) or fallback_waste
            if not waste_type:
                ward_skipped += 1
                continue
            plan_waste_ids = waste_id_list(waste_type)

            staff_template = staff_templates[idx % len(staff_templates)]
            vehicle = vehicles[idx % len(vehicles)]

            scheduled_time = BASE_TIMES[idx % len(BASE_TIMES)]
            plan, created = TripPlan.objects.update_or_create(
                company_id=company,
                project_id=project,
                staff_template_id=staff_template,
                vehicle_id=vehicle,
                waste_type_id=waste_type,
                panchayat_id=None,
                scheduled_time=scheduled_time,
                defaults={
                    **common_defaults,
                    "zone_id": ward.zone_id,
                    "waste_type_ids": plan_waste_ids,
                },
            )
            plan.wards.set([ward])
            if created:
                ward_created += 1

        # ------------------------------------------------------------------
        # Panchayat-based trip plans
        # Panchayats are rural; zone_id is not applicable (set to None).
        # ------------------------------------------------------------------
        panchayats = list(Panchayat.objects.filter(
            company_id=company, project_id=project, is_deleted=False
        ).order_by("panchayat_name")[:15])

        pan_created = pan_skipped = 0
        for idx, panchayat in enumerate(panchayats):
            waste_key = "wet" if idx % 2 == 0 else "dry"
            waste_type = waste_types.get(waste_key) or fallback_waste
            if not waste_type:
                pan_skipped += 1
                continue
            plan_waste_ids = waste_id_list(
                waste_types.get("wet") or waste_type,
                waste_types.get("dry") or waste_type,
            ) or waste_id_list(waste_type)

            staff_template = staff_templates[idx % len(staff_templates)]
            vehicle = vehicles[idx % len(vehicles)]

            scheduled_time = BASE_TIMES[idx % len(BASE_TIMES)]
            plan, created = TripPlan.objects.update_or_create(
                company_id=company,
                project_id=project,
                staff_template_id=staff_template,
                vehicle_id=vehicle,
                waste_type_id=waste_type,
                panchayat_id=panchayat,
                scheduled_time=scheduled_time,
                defaults={
                    **common_defaults,
                    "zone_id": None,
                    "waste_type_ids": plan_waste_ids,
                },
            )
            plan.wards.clear()
            if created:
                pan_created += 1

        # ------------------------------------------------------------------
        # Household-collection trip plan
        # No seeder had ever created a household-collection TripPlan before —
        # every plan above defaults to bin_collection — so the
        # WasteCollection ("Household Collections") screen had no source
        # data. Scoped to "Ward 1" to match CustomerCreationSeeder, whose
        # 15 demo customers all live in that ward.
        # ------------------------------------------------------------------
        household_ward = Ward.objects.filter(ward_name="Ward 1").first()
        household_created = False
        if household_ward and staff_templates and vehicles:
            household_staff_template = staff_templates[-1]
            household_vehicle = vehicles[-1]
            household_waste_type = waste_types.get("wet") or fallback_waste

            household_plan, household_created = TripPlan.objects.update_or_create(
                company_id=company,
                project_id=project,
                staff_template_id=household_staff_template,
                vehicle_id=household_vehicle,
                waste_type_id=household_waste_type,
                panchayat_id=None,
                scheduled_time=time(9, 0),
                collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
                defaults={
                    **common_defaults,
                    "zone_id": household_ward.zone_id,
                    "waste_type_ids": waste_id_list(household_waste_type),
                },
            )
            household_plan.wards.set([household_ward])
            TripPlanCollectionPoint.objects.get_or_create(
                trip_plan_id=household_plan,
                sequence=1,
                defaults={
                    "collection_type": TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
                    "is_active": True,
                },
            )
        else:
            self.log("Household trip plan skipped (missing 'Ward 1', staff templates, or vehicles).")

        self.log(
            f"---TripPlan seeded | ward plans created={ward_created}/{len(wards)} skipped={ward_skipped}"
            f" | panchayat plans created={pan_created}/{len(panchayats)} skipped={pan_skipped}"
            f" | household plan created={household_created}---"
        )
