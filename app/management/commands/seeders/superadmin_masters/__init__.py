from .blue_planet import BluePlanetSeeder
from .developer import PlatformDeveloperSeeder
from .superuser import PlatformSuperUserSeeder

# Only Blue Planet is seeded. The generic CompanySeeder/ProjectSeeder (which
# bootstrapped an "IWMS" demo company) were never registered here and have
# been removed, so `seed all` produces exactly one company.
COMPANY_SEEDERS = [
    BluePlanetSeeder,
]

PLATFORM_SEEDERS = [
    PlatformSuperUserSeeder,
    PlatformDeveloperSeeder,
]

SUPERADMIN_MASTER_SEEDERS = COMPANY_SEEDERS + PLATFORM_SEEDERS
