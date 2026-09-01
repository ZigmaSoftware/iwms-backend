from .blue_planet import BluePlanetSeeder
from .developer import PlatformDeveloperSeeder
from .superuser import PlatformSuperUserSeeder

# Only Blue Planet is seeded by default — CompanySeeder/ProjectSeeder (the
# generic "IWMS" demo company) and the generic ProjectSeeder are
# intentionally left unregistered here so `seed all` produces exactly one
# company. The files still exist on disk and can be imported directly if
# ever needed again.
COMPANY_SEEDERS = [
    BluePlanetSeeder,
]

PLATFORM_SEEDERS = [
    PlatformSuperUserSeeder,
    PlatformDeveloperSeeder,
]

SUPERADMIN_MASTER_SEEDERS = COMPANY_SEEDERS + PLATFORM_SEEDERS
