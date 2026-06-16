from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0004_repair_schedule_master_schema_drift"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="attendance_api_key",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="attendance_api_url",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
    ]
