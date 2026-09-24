from rest_framework import serializers
from django.db.models import ForeignKey as ForeignKeyRelatedField


class NameOrUniqueIdField(serializers.SlugRelatedField):
    """A field that WRITES via either the opaque `unique_id`
    or the master's human-readable name, but keeps READING as `unique_id`.

    Every master table's real primary key is a generated, unguessable string
    (e.g. ``COUNTRY-1997a2f3c9e412345``), so asking an Excel-upload user (or
    an API client) for it is unusable — this field lets a write use the name
    instead ("India" for `country_id`):

    * **Write** (API POST/PUT, Excel bulk upload): accepts either the
      `unique_id` or the master's `name_field` (case-insensitive). An
      explicit `unique_id` always wins over a name match. When
      `scope_fields` is given, a name match is tried scoped to those sibling
      attrs first (so "Dry Waste" resolves to the uploading company/project's
      own row, not some other tenant's identically named one), then falls
      back to an unscoped match if nothing scoped is found.
    * **Read** (API GET, Excel export/download) returns `unique_id`.

    `scope_fields` names sibling fields *on the same serializer* (e.g.
    ``["company_id", "project_id"]``) — their validated values are read from
    `parent.initial_data`/context at lookup time via the owning serializer's
    `_scope_lookup_values`, so this field doesn't need direct access to
    other fields' validated values (DRF validates fields independently).
    """

    default_error_messages = {
        "does_not_exist": (
            "No {model_name} found matching '{value}'. "
            "Enter either the exact name or the unique ID."
        ),
    }

    def __init__(self, *args, name_field="name", scope_fields=None, **kwargs):
        self.name_field = name_field
        self.scope_fields = list(scope_fields or [])
        kwargs.setdefault("slug_field", "unique_id")
        kwargs.setdefault("required", False)
        kwargs.setdefault("allow_null", True)
        super().__init__(*args, **kwargs)

    def _scope_values(self):
        """Sibling FK values already resolved on the parent serializer's
        instance/initial input, used to scope a name match to one tenant."""
        values = {}
        parent = getattr(self, "parent", None)
        initial_data = getattr(parent, "initial_data", None) or {}
        instance = getattr(parent, "instance", None)
        for field_name in self.scope_fields:
            raw = None
            if isinstance(initial_data, dict) and field_name in initial_data:
                raw = initial_data.get(field_name)
            if raw in (None, ""):
                raw = getattr(instance, field_name, None)
            if raw not in (None, ""):
                values[field_name] = raw
        return values

    def to_internal_value(self, data):
        value = str(data).strip() if data is not None else ""
        if not value:
            return None

        queryset = self.get_queryset()
        if queryset is None:
            self.fail("does_not_exist", model_name="RelatedModel", value=value)

        # Try exact slug_field (unique_id, or a custom override) match first
        exact = queryset.filter(**{self.slug_field: value}).first()
        if exact:
            return self._finalize(exact)

        # Try name match (with optional scoping)
        base_lookup = {f"{self.name_field}__iexact": value}

        scope_values = self._scope_values()
        if scope_values:
            scoped = queryset.filter(**base_lookup, **scope_values).first()
            if scoped:
                return self._finalize(scoped)

        unscoped = queryset.filter(**base_lookup).first()
        if unscoped:
            return self._finalize(unscoped)

        self.fail("does_not_exist", model_name=self._model_name(), value=value)

    def _finalize(self, instance):
        """Return the resolved instance as-is when the backing model field is
        a real ForeignKey (Django needs the instance to save it); return its
        `unique_id` string when the backing field is anything else (e.g. a
        plain CharField holding the parent's unique_id), since assigning an
        instance there would silently `str()` it via the wrong `__str__`."""
        if self._backing_field_is_foreign_key():
            return instance
        return getattr(instance, self.slug_field)

    def _backing_field_is_foreign_key(self):
        parent = getattr(self, "parent", None)
        model = getattr(getattr(parent, "Meta", None), "model", None)
        if model is None or not self.field_name:
            return True
        try:
            model_field = model._meta.get_field(self.source or self.field_name)
        except Exception:
            return True
        return isinstance(model_field, ForeignKeyRelatedField)

    def to_representation(self, value):
        """Return the unique_id for read operations."""
        if value is None:
            return None
        if hasattr(value, 'unique_id'):
            return value.unique_id
        return str(value)

    def _model_name(self):
        return self.get_queryset().model.__name__


def resolve_by_name_or_id(queryset, value, name_field="name", slug_field="unique_id"):
    """Same unique_id-then-name lookup as `NameOrUniqueIdField.to_internal_value`,
    for plain (non-serializer-field) call sites — e.g. `CompanyScopedViewSet`'s
    superadmin branch, which resolves `company_id`/`project_id` straight from
    the raw request body ahead of the serializer, so a `NameOrUniqueIdField`
    declared on the serializer never gets a chance to run for those two.

    Returns the matching instance, or None if nothing matched either lookup.
    """
    value = str(value).strip() if value is not None else ""
    if not value:
        return None

    exact = queryset.filter(**{slug_field: value}).first()
    if exact:
        return exact

    return queryset.filter(**{f"{name_field}__iexact": value}).first()