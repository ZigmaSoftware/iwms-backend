"""
Generic cascading soft-delete.

A model that inherits BaseMaster can declare:

    CASCADE_SOFT_DELETE = ("wards", "block_panchayat_unions")

— a tuple of reverse-relation accessor names on that model. When an
instance is soft-deleted, every related object reachable through those
accessors is soft-deleted too, recursively (a child's own
CASCADE_SOFT_DELETE is walked in turn), deduplicated by (model, pk), and
applied as one bulk UPDATE per model touched inside a single transaction.

BaseMaster.delete() calls cascade_soft_delete() itself, so any model that
inherits it and declares CASCADE_SOFT_DELETE gets this for free.
"""
from collections import defaultdict
from django.db import transaction


_AUDIT_RELATED_NAMES = {"created_by", "updated_by"}


def _related_objects(instance, accessor_name):
    """Normalizes a declared accessor to a list of objects.

    Most accessors are reverse FK/M2M managers (`.all()`). A reverse
    one-to-one accessor instead returns a single object directly, and
    raises <Model>.DoesNotExist if nothing is linked.
    """
    related = getattr(instance, accessor_name, None)
    if related is None:
        return []

    if hasattr(related, "all"):
        return list(related.all())

    # Reverse one-to-one: `related` is already the object itself, but
    # accessing it can have raised DoesNotExist before we got here — that
    # happens inside the getattr above and is handled by the caller.
    return [related]


def _get_related_safely(instance, accessor_name):
    try:
        return _related_objects(instance, accessor_name)
    except Exception as exc:
        # Reverse one-to-one accessors raise <Model>.DoesNotExist when
        # nothing is linked. Any other exception type is a real bug, not
        # an absent relation, and should not be swallowed.
        if exc.__class__.__name__ == "DoesNotExist":
            return []
        raise


def _model_supports_soft_delete(model):
    return (
        _model_has_field(model, "is_deleted")
        or _model_has_field(model, "is_active")
        or _model_has_field(model, "active_status")
    )


def _declared_cascade_accessors(instance):
    return tuple(getattr(instance, "CASCADE_SOFT_DELETE", ()))


def _cascade_accessors(instance):
    return _declared_cascade_accessors(instance)


def _collect_cascade_graph(instance, seen):
    """Depth-first walk of instance's CASCADE_SOFT_DELETE graph.

    `seen` maps model class -> set of pks already visited, so a row
    reachable via two different paths is only ever queued once.
    """
    key = (type(instance), instance.pk)
    model_seen = seen.setdefault(type(instance), set())
    if instance.pk in model_seen:
        return
    model_seen.add(instance.pk)

    for accessor_name in _cascade_accessors(instance):
        for child in _get_related_safely(instance, accessor_name):
            if child.pk in seen.get(type(child), ()):
                continue
            _collect_cascade_graph(child, seen)


def collect_cascade_targets(instance):
    """Returns {model_class: set(pks)} for instance's whole cascade graph, not including instance itself."""
    seen = {}
    _collect_cascade_graph(instance, seen)
    root_seen = seen.get(type(instance))
    if root_seen is not None:
        root_seen.discard(instance.pk)
        if not root_seen:
            seen.pop(type(instance), None)
    return {model: pks for model, pks in seen.items() if pks}


@transaction.atomic
def cascade_soft_delete(instance, updated_by=None):
    """Soft-deletes instance and every object in its CASCADE_SOFT_DELETE graph.

    Applies as one bulk UPDATE per model class touched (plus one for
    instance's own model), stamping updated_by when the model has that
    field. instance itself is left as a normal Python object the caller
    can still use afterward — only its DB row is updated via the bulk
    query, mirroring every other model's rows.
    """
    targets = collect_cascade_targets(instance)

    all_models = defaultdict(set)
    all_models[type(instance)].add(instance.pk)
    for model, pks in targets.items():
        all_models[model].update(pks)

    for model, pks in all_models.items():
        update_fields = {}
        if _model_has_field(model, "is_deleted"):
            update_fields["is_deleted"] = True
        if _model_has_field(model, "is_active"):
            update_fields["is_active"] = False
        if _model_has_field(model, "active_status"):
            update_fields["active_status"] = False
        if updated_by is not None and _model_has_field(model, "updated_by"):
            update_fields["updated_by"] = updated_by
        if update_fields:
            model.objects.filter(pk__in=pks).update(**update_fields)

    instance.is_deleted = True
    if _model_has_field(type(instance), "is_active"):
        instance.is_active = False
    if _model_has_field(type(instance), "active_status"):
        instance.active_status = False
    if updated_by is not None and _model_has_field(type(instance), "updated_by"):
        instance.updated_by = updated_by


def _model_has_field(model, field_name):
    return any(f.name == field_name for f in model._meta.fields)
