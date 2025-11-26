from .masters.continent_serializer import ContinentSerializer
from .masters.country_serializer import CountrySerializer
from .masters.state_serializer import StateSerializer
from .masters.district_serializer import DistrictSerializer
from .masters.city_serializer import CitySerializer
from .masters.zone_serializer import ZoneSerializer
from .masters.ward_serializer import WardSerializer

from .assets.fuel_serializer import FuelSerializer
from .assets.property_serializer import PropertySerializer
from .assets.subproperty_serializer import SubPropertySerializer

from .customers.customercreation_serializer import CustomerCreationSerializer
from .customers.wastecollection_serializer import WasteCollectionSerializer
from .customers.feedback_serializer import FeedBackSerializer

from .users.usertype_serializer import UserTypeSerializer
from .users.user_serializer import UserSerializer
from .users.userscreen_serializer import UserScreenSerializer
from .users.mainuserscreen_serializer import MainUserScreenSerializer
from .users.userpermission_serializer import UserPermissionSerializer
from .users.login_serializer import LoginSerializer

from .vehicles.vehicletypecreation_serializer import VehicleTypeCreationSerializer
from .vehicles.vehiclecreation_serializer import VehicleCreationSerializer

from .complaints.complaint_serializer import ComplaintSerializer


