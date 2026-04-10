from .alternative_staff_template_seeder import AlternativeStaffTemplateSeeder
from .auth_user_seeder import AuthUserSeeder
from .staff_office import StaffOfficeSeeder
from .staff_personal import StaffPersonalSeeder
from .staff_template_seeder import StaffTemplateSeeder
from .supervisor_zone_map import SupervisorZoneMapSeeder
from .unassigned_staff_pool import UnassignedStaffPoolSeeder

USER_CREATION_SEEDERS = [
    StaffOfficeSeeder,
    StaffPersonalSeeder,
    SupervisorZoneMapSeeder,
]

STAFF_TEMPLATE_SEEDERS = [
    AuthUserSeeder,
    StaffTemplateSeeder,
    AlternativeStaffTemplateSeeder,
]

LATE_USER_CREATION_SEEDERS = [
    UnassignedStaffPoolSeeder,
]
