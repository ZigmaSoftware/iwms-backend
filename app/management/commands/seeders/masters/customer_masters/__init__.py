# core/management/commands/seeders/masters/customer_masters/__init__.py
from .customerCreation import CustomerCreationSeeder
from .userChargeRule import UserChargeRuleSeeder

CUSTOMER_SEEDERS = [
    CustomerCreationSeeder,
    UserChargeRuleSeeder,
]
