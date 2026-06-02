from .auth_user_seeder import AuthUserSeeder
from .staff_office import StaffOfficeSeeder
from .staff_personal import StaffPersonalSeeder
from .supervisor_zone_map import SupervisorZoneMapSeeder
from .unassigned_staff_pool import UnassignedStaffPoolSeeder

USER_CREATION_SEEDERS = [
    StaffOfficeSeeder,
    StaffPersonalSeeder,
    SupervisorZoneMapSeeder,
]

STAFF_TEMPLATE_SEEDERS = [
    AuthUserSeeder,
]

LATE_USER_CREATION_SEEDERS = [
    UnassignedStaffPoolSeeder,
]
