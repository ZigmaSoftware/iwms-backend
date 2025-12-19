# seeders/role_assign/__init__.py
from .userType import UserTypeSeeder
from .staffUserType import StaffUserTypeSeeder

ROLE_ASSIGN_SEEDERS = [
    UserTypeSeeder,
    StaffUserTypeSeeder,
]
