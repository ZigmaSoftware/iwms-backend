from django.db import migrations


def create_missing_household_waste_types_table(apps, schema_editor):
    daily_trip_assignment = apps.get_model("app", "DailyTripAssignment")
    field = daily_trip_assignment._meta.get_field("household_waste_type_ids")
    through_model = field.remote_field.through
    table_name = through_model._meta.db_table

    if table_name not in schema_editor.connection.introspection.table_names():
        schema_editor.create_model(through_model)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("app", "0002_blockpanchayatunion_panchayat_block_id_municipality_and_more"),
    ]

    operations = [
        migrations.RunPython(
            create_missing_household_waste_types_table,
            migrations.RunPython.noop,
        ),
    ]
