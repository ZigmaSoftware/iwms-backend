# core/management/commands/seeders/masters/customer_masters/__init__.py
from .customerCreation import CustomerCreationSeeder
from .noidaCustomerImport import NoidaCustomerImportSeeder

CUSTOMER_SEEDERS = [
    CustomerCreationSeeder,
    NoidaCustomerImportSeeder,
]
