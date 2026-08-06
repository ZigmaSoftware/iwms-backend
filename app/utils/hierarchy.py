"""Flat-geo copy helper shared by trip-plan/collection-point style models.

IWMS keeps geography as flat FKs directly on each record (state/district/
city/zone/panchayat/ward) rather than a hierarchy-node tree, and different
models spell the same concept with or without an `_id` suffix (e.g.
`Collection_point.zone_id` vs `CustomerCreation.zone`). `copy_flat_geo`
copies whichever of these fields a given `source` actually has onto the
matching field on `target`.
"""

FLAT_GEO_FIELDS = ("state", "district", "city", "zone", "panchayat", "ward")


def _fk_field_name(obj, field):
    """Return the actual model FK field name for `field` on `obj` — either
    "<field>" (e.g. CustomerCreation.zone) or "<field>_id" (e.g.
    Collection_point.zone_id). Returns None if neither exists."""
    cls = obj if isinstance(obj, type) else type(obj)
    model_fields = {f.name for f in cls._meta.get_fields()}
    if field in model_fields:
        return field
    if f"{field}_id" in model_fields:
        return f"{field}_id"
    return None


def _raw_pk_attr(obj, fk_field_name):
    """The attribute holding the raw pk for a FK field, e.g. "zone_id" for a
    field named "zone", or "zone_id_id" for a field literally named
    "zone_id" (IWMS's flat-geo models often name the field itself "*_id")."""
    return f"{fk_field_name}_id"


def copy_flat_geo(target, source):
    if not source:
        return
    for field in FLAT_GEO_FIELDS:
        source_field = _fk_field_name(source, field)
        target_field = _fk_field_name(target, field)
        if not source_field or not target_field:
            continue
        raw_value = getattr(source, _raw_pk_attr(source, source_field), None)
        setattr(target, _raw_pk_attr(target, target_field), raw_value)
