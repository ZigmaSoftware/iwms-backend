# core/management/commands/seeders/assets/__init__.py
from .properties import PropertySeeder
from .subproperties import SubPropertySeeder
from .fuel import FuelSeeder

ASSET_SEEDERS = [
    PropertySeeder,
    SubPropertySeeder,
    FuelSeeder,

]
