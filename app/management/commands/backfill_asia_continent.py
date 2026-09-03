from django.core.management.base import BaseCommand

from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country

SUB_REGIONS = ["South Asia", "East Asia", "Southeast Asia", "Central Asia"]


class Command(BaseCommand):
    help = (
        "Re-point countries seeded under the 'South Asia'/'East Asia'/"
        "'Southeast Asia'/'Central Asia' continent rows onto the single "
        "'Asia' continent, then soft-delete those now-empty rows. One-off "
        "fix for databases seeded before continent.py/country.py stopped "
        "treating Asian sub-regions as separate top-level continents."
    )

    def handle(self, *args, **options):
        asia, _ = Continent.objects.get_or_create(name="Asia", is_deleted=False)

        moved = 0
        removed = 0
        for region_name in SUB_REGIONS:
            region = Continent.objects.filter(name=region_name, is_deleted=False).first()
            if not region:
                continue
            moved += Country.objects.filter(continent_id=region).update(continent_id=asia)
            if not Country.objects.filter(continent_id=region).exists():
                region.delete()
                removed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Re-pointed {moved} countries onto 'Asia' and soft-deleted {removed} empty sub-region continents."
            )
        )
