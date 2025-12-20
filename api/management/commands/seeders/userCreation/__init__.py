# seeders/user_creation/__init__.py

from .staff_office import StaffOfficeSeeder
from .staff_personal import StaffPersonalSeeder
from .user import UserSeeder

USER_CREATION_SEEDERS = [
    StaffOfficeSeeder,
    StaffPersonalSeeder,
    UserSeeder,
]
