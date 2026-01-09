from .auth_user_seeder import AuthUserSeeder
from .staff_template_seeder import StaffTemplateSeeder
from .alternative_staff_template_seeder import AlternativeStaffTemplateSeeder
from ..vehicles.trip_definition import TripDefinitionSeeder

STAFF_SEEDERS = [
    AuthUserSeeder,
    StaffTemplateSeeder,
    TripDefinitionSeeder,
    AlternativeStaffTemplateSeeder,
]
