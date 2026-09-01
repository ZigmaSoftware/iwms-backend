"""Staff management seeders — office/personal details, auth users, supervisors.

Ordered by dependency: office and personal details come first, then the
auth users built from them, then the supervisor zone mapping.
"""

from .staff_office import StaffOfficeSeeder
from .staff_personal import StaffPersonalSeeder
from .auth_user_seeder import AuthUserSeeder
from .supervisor_user import SupervisorUserSeeder

STAFF_MANAGEMENT_SEEDERS = [
    StaffOfficeSeeder,
    StaffPersonalSeeder,
    AuthUserSeeder,
    SupervisorUserSeeder,
]

__all__ = [
    "StaffOfficeSeeder",
    "StaffPersonalSeeder",
    "AuthUserSeeder",
    "SupervisorUserSeeder",
    "STAFF_MANAGEMENT_SEEDERS",
]
