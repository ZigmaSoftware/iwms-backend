from django.db import migrations, models
import django.db.models.deletion


def backfill_approved_vehicle_breakdowns(apps, schema_editor):
    VehicleBreakdown = apps.get_model("app", "VehicleBreakdown")
    BinCollectionEvent = apps.get_model("app", "BinCollectionEvent")

    approved_breakdowns = VehicleBreakdown.objects.filter(
        approval_status="APPROVED",
        is_deleted=False,
    ).only("unique_id", "trip_assignment_id")

    for breakdown in approved_breakdowns.iterator():
        BinCollectionEvent.objects.filter(
            trip_assignment_id=breakdown.trip_assignment_id_id,
            is_deleted=False,
            vehicle_breakdown_id__isnull=True,
        ).update(vehicle_breakdown_id=breakdown.unique_id)


def clear_backfilled_vehicle_breakdowns(apps, schema_editor):
    BinCollectionEvent = apps.get_model("app", "BinCollectionEvent")
    BinCollectionEvent.objects.update(vehicle_breakdown_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="bincollectionevent",
            name="vehicle_breakdown_id",
            field=models.ForeignKey(
                blank=True,
                db_column="vehicle_breakdown_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bin_collection_events",
                to="app.vehiclebreakdown",
            ),
        ),
        migrations.RunPython(
            backfill_approved_vehicle_breakdowns,
            clear_backfilled_vehicle_breakdowns,
        ),
    ]
