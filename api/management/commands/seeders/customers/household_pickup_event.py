from datetime import datetime, timedelta

from django.utils import timezone

from api.management.commands.seeders.base import BaseSeeder
from api.apps.household_pickup_event import HouseholdPickupEvent
from api.apps.customercreation import CustomerCreation
from api.apps.userType import UserType
from api.apps.staffUserType import StaffUserType
from api.apps.userCreation import User
from api.apps.vehicleCreation import VehicleCreation
from api.apps.zone import Zone
from api.apps.property import Property
from api.apps.subproperty import SubProperty


class HouseholdPickupEventSeeder(BaseSeeder):
    name = "household_pickup_event"

    def run(self):
        customers = list(
            CustomerCreation.objects.filter(
                is_active=True,
                is_deleted=False,
            ).select_related("zone", "property", "sub_property")[:3]
        )
        if not customers:
            self.log("No customers found. Skipping household pickup events.")
            return

        try:
            staff_type = UserType.objects.get(name__iexact="staff")
            operator_role = StaffUserType.objects.get(
                name="operator",
                usertype_id=staff_type,
            )
        except (UserType.DoesNotExist, StaffUserType.DoesNotExist):
            self.log("Operator role missing. Skipping household pickup events.")
            return

        operator = User.objects.filter(
            staffusertype_id=operator_role,
            is_active=True,
            is_deleted=False,
        ).first()
        if not operator:
            admin_role = StaffUserType.objects.filter(
                name="admin",
                usertype_id=staff_type,
            ).first()
            if admin_role:
                operator = User.objects.filter(
                    staffusertype_id=admin_role,
                    is_active=True,
                    is_deleted=False,
                ).first()

            if operator:
                self.log("No operator user found. Using admin for pickup events.")
            else:
                operator = User.objects.filter(
                    user_type_id=staff_type,
                    is_active=True,
                    is_deleted=False,
                ).first()
                if operator:
                    self.log("No operator user found. Using first staff user.")
                else:
                    self.log("No staff user found. Skipping household pickup events.")
                    return

        vehicle = VehicleCreation.objects.filter(
            is_active=True,
            is_deleted=False,
        ).first()
        if not vehicle:
            self.log("No vehicles found. Skipping household pickup events.")
            return

        fallback_zone = Zone.objects.filter(
            is_active=True,
            is_deleted=False,
        ).first()
        fallback_property = Property.objects.filter(is_deleted=False).first()
        fallback_sub_property = SubProperty.objects.filter(is_deleted=False).first()

        if not (fallback_zone and fallback_property and fallback_sub_property):
            self.log("Missing zone/property masters. Skipping pickup events.")
            return

        seed_time = timezone.make_aware(datetime(2026, 1, 1, 8, 0, 0))

        for idx, customer in enumerate(customers):
            zone = customer.zone or fallback_zone
            property_obj = customer.property or fallback_property
            sub_property_obj = customer.sub_property or fallback_sub_property

            if not (zone and property_obj and sub_property_obj):
                continue

            pickup_time = seed_time + timedelta(minutes=15 * idx)
            source = (
                HouseholdPickupEvent.Source.HOUSEHOLD_WASTE
                if idx % 2 == 0
                else HouseholdPickupEvent.Source.HOUSEHOLD_BIN
            )

            HouseholdPickupEvent.objects.get_or_create(
                customer=customer,
                pickup_time=pickup_time,
                collector_staff=operator,
                vehicle=vehicle,
                source=source,
                defaults={
                    "zone": zone,
                    "property": property_obj,
                    "sub_property": sub_property_obj,
                    "weight_kg": 5 + idx if source == HouseholdPickupEvent.Source.HOUSEHOLD_WASTE else None,
                },
            )

        self.log("Household pickup events seeded")
