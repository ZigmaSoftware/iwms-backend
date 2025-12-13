from .apps.continent import Continent
from .apps.country import Country
from .apps.state import State
from .apps.district import District
from .apps.city import City
from .apps.zone import Zone
from .apps.ward import Ward

from .apps.fuel import Fuel
from .apps.property import Property
from .apps.subproperty import SubProperty

from .apps.staffcreation import StaffOfficeDetails, StaffPersonalDetails

from .apps.customercreation import CustomerCreation
from .apps.wastecollection import WasteCollection
from .apps.feedback import FeedBack

from .apps.userscreen import UserScreen
from .apps.userType import UserType
from .apps.staffUserType import StaffUserType
from .apps.userscreenpermission import UserScreenPermission
from .apps.userCreation import User

from .apps.vehicleTypeCreation import VehicleTypeCreation
from .apps.vehicleCreation import VehicleCreation

from .apps.complaints import Complaint

from .apps.main_category_citizenGrievance import MainCategory
from .apps.sub_category_citizenGrievance import SubCategory

from .apps.waste_collection_bluetooth import (
    WasteCollectionSub,
    WasteType,
    WasteCollectionMain
)


__all__ = [
    # Geography
    "Continent",
    "Country",
    "State",
    "District",
    "City",
    "Zone",
    "Ward",

    # Assets
    "Fuel",
    "Property",
    "SubProperty",

    # Staff
    "StaffOfficeDetails",
    "StaffPersonalDetails",

    # Customer / Waste / Feedback
    "CustomerCreation",
    "WasteCollection",
    "FeedBack",

    # User, Access & Screens
    "User",
    "UserType",
    "StaffUserType",
    "UserScreen",
    "UserScreenPermission",

    # Vehicles
    "VehicleTypeCreation",
    "VehicleCreation",

    # Complaints
    "Complaint",

    # Citizen Grievance
    "MainCategory",
    "SubCategory",

    # Bluetooth Waste Collection
    "WasteCollectionSub",
    "WasteType",
    "WasteCollectionMain",
]
