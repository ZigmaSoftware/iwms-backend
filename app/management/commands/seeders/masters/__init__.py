from .continent import ContinentSeeder
from .country import CountrySeeder
from .state import StateSeeder
from .district import DistrictSeeder
from .city import CitySeeder
from .zone import ZoneSeeder
from .ward import WardSeeder
from .bin import BinSeeder

MASTER_SEEDERS = [
    ContinentSeeder,
    CountrySeeder,
    StateSeeder,
    DistrictSeeder,
    CitySeeder,
    ZoneSeeder,
    WardSeeder,
    BinSeeder
]
