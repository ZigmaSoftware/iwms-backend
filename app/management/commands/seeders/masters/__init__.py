from .continent import ContinentSeeder
from .country import CountrySeeder
from .state import StateSeeder
from .district import DistrictSeeder
from .city import CitySeeder
from .zone import ZoneSeeder
from .ward import WardSeeder
from .bins import BinSeeder
from .wastetype import WasteTypeSeeder
from .areatype import AreaTypeSeeder
from .hierarchy import AdministrativeHierarchySeeder
from .panchayat import PanchayatSeeder
from .collection_point import CollectionPointSeeder
from .point_collection import PointCollectionSeeder
from .weighbridge import WeighbridgeCheckSeeder
from .trip import TripSeeder

MASTER_SEEDERS = [
    ContinentSeeder,
    CountrySeeder,
    StateSeeder,
    DistrictSeeder,
    CitySeeder,
    AreaTypeSeeder,
    AdministrativeHierarchySeeder,
    ZoneSeeder,
    WardSeeder,
    PanchayatSeeder,
    WasteTypeSeeder,
    CollectionPointSeeder,
    BinSeeder,
    TripSeeder,
    PointCollectionSeeder,
    WeighbridgeCheckSeeder
]
