from .auth_user_seeder import AuthUserSeeder
from .staff_template_seeder import StaffTemplateSeeder
from .alternative_staff_template_seeder import AlternativeStaffTemplateSeeder

STAFF_SEEDERS = [
    AuthUserSeeder,
    StaffTemplateSeeder,
    AlternativeStaffTemplateSeeder,
]
