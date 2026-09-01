"""Waste masters seeders — properties, sub-properties, waste types, bins.

Ordered by dependency: sub-properties need properties, bins need the
collection points seeded in schedule_setup.

(weighbridge.py is entirely commented out and so is not exported.)
"""

from .properties import PropertySeeder
from .subproperties import SubPropertySeeder
from .wastetype import WasteTypeSeeder
from .bins import BinSeeder

WASTE_MASTER_SEEDERS = [
    PropertySeeder,
    SubPropertySeeder,
    WasteTypeSeeder,
    BinSeeder,
]

__all__ = [
    "PropertySeeder",
    "SubPropertySeeder",
    "WasteTypeSeeder",
    "BinSeeder",
    "WASTE_MASTER_SEEDERS",
]
