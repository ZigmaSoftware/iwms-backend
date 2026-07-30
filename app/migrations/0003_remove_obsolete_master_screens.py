from django.db import migrations
from django.db.models import Q


OBSOLETE_SCREEN_NAMES = (
    "area type",
    "area-type",
    "area-types",
    "areatype",
    "areatypes",
    "municipality",
    "municipalities",
    "town panchayat",
    "town-panchayat",
    "town-panchayats",
)


def remove_obsolete_master_screens(apps, schema_editor):
    UserScreen = apps.get_model("app", "UserScreen")
    UserScreenColumn = apps.get_model("app", "UserScreenColumn")
    CompanyUserScreenPermission = apps.get_model(
        "app", "CompanyUserScreenPermission"
    )
    CompanyUserScreenColumnPermission = apps.get_model(
        "app", "CompanyUserScreenColumnPermission"
    )

    obsolete_screens = UserScreen.objects.filter(
        Q(userscreen_name__in=OBSOLETE_SCREEN_NAMES)
        | Q(folder_name__in=OBSOLETE_SCREEN_NAMES)
    )
    screen_ids = list(obsolete_screens.values_list("unique_id", flat=True))
    if not screen_ids:
        return

    CompanyUserScreenColumnPermission.objects.filter(
        userscreen_id__in=screen_ids
    ).delete()
    CompanyUserScreenPermission.objects.filter(
        userscreen_id__in=screen_ids
    ).delete()
    UserScreenColumn.objects.filter(userscreen_id__in=screen_ids).delete()
    obsolete_screens.delete()


class Migration(migrations.Migration):
    dependencies = [
        (
            "app",
            "0002_remove_areatype_city_id_remove_areatype_company_id_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            remove_obsolete_master_screens,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
