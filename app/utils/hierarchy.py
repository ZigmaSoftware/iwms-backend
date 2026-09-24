"""Flat-geo copy helper shared by trip-plan/collection-point style models.

IWMS keeps geography as flat id columns directly on each record
(state_id/district_id/city_id/zone_id/panchayat_id/ward_id — plain
CharFields holding the related row's unique_id, not real ForeignKeys)
rather than a hierarchy-node tree. `copy_flat_geo` copies whichever of
these id columns a given `source` actually has onto the matching column
on `target`.
"""

FLAT_GEO_FIELDS = ("state", "district", "city", "zone", "panchayat", "ward")


def _id_field_name(obj, field):
    """Return the actual model id-column name for `field` on `obj`, e.g.
    "zone_id" for both `CustomerCreation.zone_id` and
    `Collection_point.zone_id`. Returns None if it doesn't exist."""
    cls = obj if isinstance(obj, type) else type(obj)
    model_fields = {f.name for f in cls._meta.get_fields()}
    candidate = f"{field}_id"
    return candidate if candidate in model_fields else None


def copy_flat_geo(target, source):
    if not source:
        return
    for field in FLAT_GEO_FIELDS:
        source_field = _id_field_name(source, field)
        target_field = _id_field_name(target, field)
        if not source_field or not target_field:
            continue
        setattr(target, target_field, getattr(source, source_field, None))
