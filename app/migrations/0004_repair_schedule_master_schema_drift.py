from django.db import migrations


def add_missing_field(apps, schema_editor, model_name, field_name):
    model = apps.get_model("app", model_name)
    table_name = model._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(
                cursor,
                table_name,
            )
        }

    field = model._meta.get_field(field_name)
    if field.column not in columns:
        schema_editor.add_field(model, field)


def repair_schedule_master_schema(apps, schema_editor):
    tables = set(schema_editor.connection.introspection.table_names())

    daily_household_collection = apps.get_model(
        "app",
        "DailyTripHouseholdCollection",
    )
    if daily_household_collection._meta.db_table not in tables:
        schema_editor.create_model(daily_household_collection)

    add_missing_field(
        apps,
        schema_editor,
        "TripPlanCollectionPoint",
        "collection_type",
    )
    add_missing_field(
        apps,
        schema_editor,
        "TripPlanCollectionPoint",
        "customer_id",
    )
    add_missing_field(
        apps,
        schema_editor,
        "DailyTripLog",
        "household_collected_weight_kg",
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("app", "0003_repair_daily_trip_assignment_household_waste_types"),
    ]

    operations = [
        migrations.RunPython(
            repair_schedule_master_schema,
            migrations.RunPython.noop,
        ),
    ]
