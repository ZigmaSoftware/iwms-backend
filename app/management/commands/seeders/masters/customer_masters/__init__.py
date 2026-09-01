# core/management/commands/seeders/masters/customer_masters/__init__.py
from .customerCreation import CustomerCreationSeeder
from .userChargeRule import UserChargeRuleSeeder
from .noidaCustomerImport import NoidaCustomerImportSeeder

CUSTOMER_SEEDERS = [
    CustomerCreationSeeder,
    UserChargeRuleSeeder,
    NoidaCustomerImportSeeder,
]
