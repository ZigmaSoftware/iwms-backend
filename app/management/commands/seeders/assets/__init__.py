# core/management/commands/seeders/assets/__init__.py
from .bins import BinSeeder
from .collection_point import CollectionPointSeeder
from .point_collection import PointCollectionSeeder
from .weighbridge import WeighbridgeCheckSeeder

ASSET_SEEDERS = [
    CollectionPointSeeder,
    BinSeeder,
    PointCollectionSeeder,
    WeighbridgeCheckSeeder,
]
