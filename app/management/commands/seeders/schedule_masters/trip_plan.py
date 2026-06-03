from datetime import time

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


class TripPlanSeeder(BaseSeeder):
    name = "trip_plan"

    def _resolve_staff_template(self, driver_username, operator_username):
        return (
            StaffTemplate.objects.filter(
                driver_id__username__iexact=driver_username,
                operator_id__username__iexact=operator_username,
                is_deleted=False,
            )
            .order_by("created_at")
            .first()
        )

    def run(self):
        company = Company.objects.filter(name="IWMS").first()
        project = (
            Project.objects.filter(name=f"{company.name} Main Project").first()
            if company
            else None
        )
        district = District.objects.filter(company_id=company, project_id=project).first()
        city = City.objects.filter(company_id=company, project_id=project).first()
        panchayat = Panchayat.objects.filter(
            panchayat_name="Panchayat 1",
            company_id=company,
            project_id=project,
        ).first()
        property_obj = Property.objects.filter(is_deleted=False).first()
        sub_property_obj = SubProperty.objects.filter(is_deleted=False).first()
        supervisor = Staffcreation.objects.filter(is_deleted=False).order_by("created_at").first()

        if not all([company, project, district, city, panchayat, property_obj, sub_property_obj, supervisor]):
            self.log("TripPlanSeeder skipped (missing dependencies)")
            return

        plans = [
            {
                "driver": "driver_user",
                "operator": "operator_user",
                "waste_type_name": "Wet Waste",
                "vehicle_no": "WET-VEHICLE-01",
                "scheduled_time": time(7, 0),
            },
            {
                "driver": "driver2_user",
                "operator": "operator2_user",
                "waste_type_name": "Dry Waste",
                "vehicle_no": "DRY-VEHICLE-01",
                "scheduled_time": time(7, 30),
            },
        ]

        created_count = 0
        skipped = 0
        TripPlan.objects.filter(
            company_id=company,
            project_id=project,
            status=TripPlan.Status.ACTIVE,
        ).update(approval_status=TripPlan.ApprovalStatus.APPROVED)
        for plan in plans:
            staff_template = self._resolve_staff_template(plan["driver"], plan["operator"])
            waste_type = WasteType.objects.filter(
                waste_type_name__iexact=plan["waste_type_name"],
                is_deleted=False,
            ).first()
            vehicle = VehicleCreation.objects.filter(
                vehicle_no=plan["vehicle_no"],
                is_deleted=False,
            ).first()
            if not vehicle:
                vehicle = VehicleCreation.objects.filter(
                    company_id=company,
                    project_id=project,
                    is_deleted=False,
                ).order_by("created_at").first()

            if not all([staff_template, waste_type, vehicle]):
                self.log(
                    f"TripPlan skipped: template={staff_template} "
                    f"waste={waste_type} vehicle={vehicle}"
                )
                skipped += 1
                continue

            _, created = TripPlan.objects.get_or_create(
                company_id=company,
                project_id=project,
                staff_template_id=staff_template,
                vehicle_id=vehicle,
                waste_type_id=waste_type,
                defaults={
                    "district_id": district,
                    "city_id": city,
                    "panchayat_id": panchayat,
                    "supervisor_id": supervisor,
                    "property_id": property_obj,
                    "sub_property_id": sub_property_obj,
                    "trip_trigger_weight_kg": 800,
                    "max_vehicle_capacity_kg": 3000,
                    "scheduled_time": plan["scheduled_time"],
                    "approval_status": TripPlan.ApprovalStatus.APPROVED,
                    "status": TripPlan.Status.ACTIVE,
                },
            )
            if created:
                created_count += 1

        self.log(
            f"---TripPlan seeded | created={created_count} | skipped={skipped}---"
        )
