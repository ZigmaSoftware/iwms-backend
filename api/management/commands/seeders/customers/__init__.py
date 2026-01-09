# core/management/commands/seeders/customers/__init__.py
from .customerCreation import CustomerCreationSeeder
from .household_pickup_event import HouseholdPickupEventSeeder

CUSTOMER_SEEDERS = [
    CustomerCreationSeeder,
    HouseholdPickupEventSeeder,
]
