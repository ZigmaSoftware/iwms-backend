# core/management/commands/seeders/customers/__init__.py
from .customerCreation import CustomerCreationSeeder

CUSTOMER_SEEDERS = [
    CustomerCreationSeeder,
]
