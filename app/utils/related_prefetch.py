"""Batch-resolve string pseudo-FKs when a serializer renders a list.

Most models here store relations as a plain CharField holding the parent's
unique_id, so select_related/prefetch_related can't follow them and every
`obj.ward` / `Ward.objects.filter(unique_id=obj.ward_id).first()` in a
serializer runs one query per row. `prefetching_list_serializer` builds a
ListSerializer that loads each related table once for the whole page and
attaches the rows to each instance; `related()` reads them back, falling back
to a single lookup when the object is serialized on its own.

A lookup maps an attr name to `(model, id_field)`, or `(model, id_field,
key_field)` when the parent is keyed on something other than `unique_id`
(e.g. staff on `staff_unique_id`).
"""

from rest_framework import serializers


def prefetch_related_rows(instances, lookups):
    """Load every relation in `lookups` for `instances` (one query per
    relation) and attach them for `related()` to read."""
    instances = [obj for obj in instances if obj is not None]

    rows_by_attr = {}
    for attr, (model, id_field, *key) in lookups.items():
        key_field = key[0] if key else "unique_id"
        ids = {getattr(obj, id_field) for obj in instances if getattr(obj, id_field)}
        rows_by_attr[attr] = (
            {
                getattr(row, key_field): row
                for row in model.objects.filter(**{f"{key_field}__in": ids})
            }
            if ids else {}
        )

    for obj in instances:
        cache = getattr(obj, "_related_cache", None) or {}
        for attr, (_, id_field, *_key) in lookups.items():
            cache[attr] = rows_by_attr[attr].get(getattr(obj, id_field))
        obj._related_cache = cache

    return rows_by_attr


def prefetching_list_serializer(lookups):
    class PrefetchingListSerializer(serializers.ListSerializer):
        def to_representation(self, data):
            instances = list(data.all() if hasattr(data, "all") else data)
            prefetch_related_rows(instances, lookups)
            return super().to_representation(instances)

    return PrefetchingListSerializer


def cached_related(obj, attr):
    """`related()` that also remembers a single-object lookup on `obj`, for
    serializers whose fields read the same relation several times."""
    cache = obj.__dict__.setdefault("_related_cache", {})
    if attr not in cache:
        cache[attr] = getattr(obj, attr, None)
    return cache[attr]


def related(obj, attr, model=None, id_field=None):
    """Prefetched relation when rendered as a list, else a single lookup —
    via `model`/`id_field` when given, otherwise the model's own accessor."""
    cache = getattr(obj, "_related_cache", None)
    if cache is not None and attr in cache:
        return cache[attr]
    if model is not None:
        value = getattr(obj, id_field)
        return model.objects.filter(unique_id=value).first() if value else None
    return getattr(obj, attr, None)
