from django.db import migrations, models


def backfill_scoped_display_ids(apps, schema_editor):
    CustomerCreation = apps.get_model("app", "CustomerCreation")
    StaffcreationOfficeDetails = apps.get_model(
        "app", "StaffcreationOfficeDetails"
    )

    def backfill(model, field_name, prefix):
        counters = {}
        records = model.objects.order_by(
            "company_id_id", "project_id_id", model._meta.pk.name
        )
        pending = []
        for record in records.iterator():
            scope = (record.company_id_id, record.project_id_id)
            counters[scope] = counters.get(scope, 0) + 1
            setattr(record, field_name, f"{prefix}{counters[scope]:04d}")
            pending.append(record)

            if len(pending) == 1000:
                model.objects.bulk_update(pending, [field_name])
                pending = []

        if pending:
            model.objects.bulk_update(pending, [field_name])

    backfill(CustomerCreation, "customer_id", "CUST")
    backfill(StaffcreationOfficeDetails, "staff_id", "STF")


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0002_remove_dailytriphouseholdcollection_uniq_household_per_trip_assignment_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="customercreation",
            name="customer_id",
            field=models.CharField(
                db_index=True, editable=False, max_length=20, null=True
            ),
        ),
        migrations.AddField(
            model_name="staffcreationofficedetails",
            name="staff_id",
            field=models.CharField(
                db_index=True, editable=False, max_length=20, null=True
            ),
        ),
        migrations.RunPython(
            backfill_scoped_display_ids,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="customercreation",
            name="customer_id",
            field=models.CharField(db_index=True, editable=False, max_length=20),
        ),
        migrations.AlterField(
            model_name="staffcreationofficedetails",
            name="staff_id",
            field=models.CharField(db_index=True, editable=False, max_length=20),
        ),
        migrations.AddConstraint(
            model_name="customercreation",
            constraint=models.UniqueConstraint(
                fields=("company_id", "project_id", "customer_id"),
                name="uniq_customer_id_per_company_project",
            ),
        ),
        migrations.AddConstraint(
            model_name="staffcreationofficedetails",
            constraint=models.UniqueConstraint(
                fields=("company_id", "project_id", "staff_id"),
                name="uniq_staff_id_per_company_project",
            ),
        ),
    ]
