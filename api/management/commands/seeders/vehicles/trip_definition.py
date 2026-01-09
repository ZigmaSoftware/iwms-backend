from api.management.commands.seeders.base import BaseSeeder
from api.apps.trip_definition import TripDefinition
from api.apps.routeplan import RoutePlan
from api.apps.stafftemplate import StaffTemplate
from api.apps.property import Property
from api.apps.subproperty import SubProperty


class TripDefinitionSeeder(BaseSeeder):
    name = "trip_definition"

    def run(self):
        routeplan = RoutePlan.objects.first()
        staff_template = (
            StaffTemplate.objects.filter(
                status="ACTIVE",
                approval_status="APPROVED",
            )
            .order_by("created_at")
            .first()
        )
        if not staff_template:
            staff_template = StaffTemplate.objects.order_by("created_at").first()
        property_obj = Property.objects.filter(is_deleted=False).first()
        sub_property_obj = SubProperty.objects.filter(is_deleted=False).first()

        if not all([routeplan, staff_template, property_obj, sub_property_obj]):
            self.log("❌ TripDefinitionSeeder skipped (missing dependencies)")
            return

        trip_def, created = TripDefinition.objects.get_or_create(
            routeplan=routeplan,
            staff_template=staff_template,
            property=property_obj,
            sub_property=sub_property_obj,
            defaults={
                "trip_trigger_weight_kg": 800,
                "max_vehicle_capacity_kg": 3000,
                "status": TripDefinition.Status.ACTIVE,
                "approval_status": TripDefinition.ApprovalStatus.APPROVED,
            }
        )

        if not created and trip_def.approval_status != TripDefinition.ApprovalStatus.APPROVED:
            trip_def.approval_status = TripDefinition.ApprovalStatus.APPROVED
            trip_def.status = TripDefinition.Status.ACTIVE
            trip_def.save(update_fields=["approval_status", "status"])

        self.log("✅ TripDefinition seeded")
