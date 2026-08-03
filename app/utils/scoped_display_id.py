from django.db.models import IntegerField, Max
from django.db.models.functions import Cast, Substr


def lock_tenant_scope(*, company_model, project_model, company_id, project_id):
    """Lock one stable tenant row before allocating the next display ID."""
    if project_id:
        project_model.objects.select_for_update().only("pk").get(pk=project_id)
    elif company_id:
        company_model.objects.select_for_update().only("pk").get(pk=company_id)


def next_scoped_display_id(
    *, model, field_name, prefix, company_id, project_id
):
    """Return the next PREFIX0001-style ID within a company/project scope."""
    queryset = model.objects.filter(
        company_id_id=company_id,
        project_id_id=project_id,
    ).exclude(**{f"{field_name}__isnull": True})

    max_sequence = (
        queryset.annotate(
            display_id_sequence=Cast(
                Substr(field_name, len(prefix) + 1),
                IntegerField(),
            )
        ).aggregate(value=Max("display_id_sequence"))["value"]
        or 0
    )
    return f"{prefix}{max_sequence + 1:04d}"
