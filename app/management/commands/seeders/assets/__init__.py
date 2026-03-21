# core/management/commands/seeders/assets/__init__.py
from .bins import BinSeeder
from .collection_point import CollectionPointSeeder
from .point_collection import PointCollectionSeeder
from .weighbridge import WeighbridgeCheckSeeder

ASSET_SEEDERS = [
<<<<<<< HEAD
    CollectionPointSeeder,
    BinSeeder,
    PointCollectionSeeder,
    WeighbridgeCheckSeeder,
=======
    PropertySeeder,
    SubPropertySeeder,
    FuelSeeder,
>>>>>>> 3a5ccbb6b51fc7abd0932f7078538d0a81e8293c
]
