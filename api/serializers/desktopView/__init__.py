
# Masters
from .masters.continent_serializer import ContinentSerializer
from .masters.country_serializer import CountrySerializer
from .masters.state_serializer import StateSerializer
from .masters.district_serializer import DistrictSerializer
from .masters.city_serializer import CitySerializer
from .masters.zone_serializer import ZoneSerializer
from .masters.ward_serializer import WardSerializer

# Assets
from .assets.fuel_serializer import FuelSerializer
from .assets.property_serializer import PropertySerializer
from .assets.subproperty_serializer import SubPropertySerializer

# Customers
from .customers.customercreation_serializer import CustomerCreationSerializer
from .customers.wastecollection_serializer import WasteCollectionSerializer
from .customers.feedback_serializer import FeedBackSerializer
# Users
from .users.usertype_serializer import UserTypeSerializer
from .users.user_serializer import UserSerializer
from .users.userscreen_serializer import UserScreenSerializer
from .users.login_serializer import LoginSerializer
from .users.userscreenaction_serializer import UserScreenActionSerializer
from .users.mainscreentype_serializer import MainScreenTypeSerializer
from .users.mainscreen_serializer import MainScreenSerializer
from .users.userscreenpermission_serializer import (
    UserScreenPermissionSerializer,
    UserScreenPermissionMultiScreenSerializer,
    ScreenActionSerializer
)
from .users.stafftemplate_serializer import StaffTemplateSerializer
from .users.staff_template_audit_log_serializer import StaffTemplateAuditLogSerializer
from .users.alternative_stafftemplate_serializer import AlternativeStaffTemplateSerializer
from .users.unassigned_staff_pool_serializer import UnassignedStaffPoolSerializer
from .users.trip_attendance_serializer import TripAttendanceSerializer
# Vehicles
from .vehicles.vehicletypecreation_serializer import VehicleTypeCreationSerializer
from .vehicles.vehicleCreation_serializer import VehicleCreationSerializer
from .vehicles.trip_instance_serializer import TripInstanceSerializer
from .vehicles.vehicle_trip_audit_serializer import VehicleTripAuditSerializer
from .vehicles.trip_exception_log_serializer import TripExceptionLogSerializer

# Complaints
from .complaints.complaint_serializer import ComplaintSerializer
