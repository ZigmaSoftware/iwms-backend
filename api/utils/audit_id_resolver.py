# api/utils/audit_id_resolver.py

from django.db.models import Q

from api.apps.userscreen import UserScreen
from api.apps.userscreenaction import UserScreenAction


ACTION_SYNONYMS = {
    "add": ("add", "create"),
    "edit": ("edit", "update"),
    "delete": ("delete", "remove"),
    "view": ("view", "read"),
}


def get_audit_ids(*, module_slug, resource_slug, resource_name, action):
    userscreen = _resolve_user_screen(module_slug, resource_slug, resource_name)
    if not userscreen:
        return None

    action_obj = _resolve_action(action)
    if not action_obj:
        return None

    # IMPORTANT: return FK IDs, not semantic fields
    return (
        userscreen.mainscreen_id_id,
        userscreen.unique_id,
        action_obj.unique_id,
    )


# --------------------------------------------------
# USER SCREEN RESOLUTION
# --------------------------------------------------
def _resolve_user_screen(module_slug, resource_slug, resource_name):
    """
    Resolve UserScreen using semantic fields:
    - folder_name (router slug)
    - userscreen_name (class name)
    """

    candidates = list(_candidate_terms(
        resource_slug,                   # continents
        _singularize(resource_slug),     # continent
        resource_name,                   # Continent
    ))

    if not candidates:
        return None

    base_qs = UserScreen.objects.filter(is_deleted=False)

    # ---- Module scoping (via MainScreen.icon_name / name) ----
    if module_slug:
        module_q = _build_module_filter(module_slug)
        scoped_qs = base_qs.filter(module_q)
    else:
        scoped_qs = base_qs

    return _match_from_queryset(
        scoped_qs,
        fields=("folder_name", "userscreen_name"),
        candidates=candidates,
        only_fields=("unique_id", "mainscreen_id"),
    )


# --------------------------------------------------
# ACTION RESOLUTION
# --------------------------------------------------
def _resolve_action(action):
    if not action:
        return None

    synonyms = ACTION_SYNONYMS.get(action.lower(), ())
    candidates = list(_candidate_terms(action, *synonyms))
    if not candidates:
        return None

    return _match_from_queryset(
        UserScreenAction.objects.filter(is_deleted=False),
        fields=("variable_name", "action_name"),
        candidates=candidates,
        only_fields=("unique_id",),
    )


# --------------------------------------------------
# GENERIC MATCHER
# --------------------------------------------------
def _match_from_queryset(queryset, *, fields, candidates, only_fields=()):
    if only_fields:
        queryset = queryset.only(*only_fields)

    for value in candidates:
        if not value:
            continue

        for field in fields:
            match = (
                queryset
                .filter(**{f"{field}__iexact": value})
                .order_by("unique_id")
                .first()
            )
            if match:
                return match

    return None


# --------------------------------------------------
# MODULE → MAINSCREEN FILTER
# --------------------------------------------------
def _build_module_filter(module_slug):
    """
    Resolve module using MainScreen semantic fields
    (icon_name / mainscreen_name), NOT unique_id
    """
    terms = list(_candidate_terms(module_slug, _singularize(module_slug)))

    module_filter = Q()
    for term in terms:
        module_filter |= Q(mainscreen_id__icon_name__iexact=term)
        module_filter |= Q(mainscreen_id__mainscreen_name__iexact=term)

    return module_filter


# --------------------------------------------------
# STRING HELPERS
# --------------------------------------------------
def _candidate_terms(*values):
    seen = set()
    for raw in values:
        for variant in _normalize_variants(raw):
            if variant not in seen:
                seen.add(variant)
                yield variant


def _normalize_variants(value):
    if not value:
        return []

    raw = value.strip()
    normalized = raw.replace("_", " ").replace("-", " ").strip()
    tokens = [t for t in normalized.split() if t]

    variants = {
        raw,
        raw.lower(),
        raw.title(),
        normalized,
        normalized.lower(),
        normalized.title(),
        "".join(tokens),
        "".join(tokens).lower(),
        "".join(tokens).title(),
    }

    return [v for v in variants if v]


def _singularize(value):
    if not value:
        return ""
    word = value.strip()
    lower = word.lower()

    if lower.endswith("ies"):
        return word[:-3] + "y"
    if lower.endswith("s") and not lower.endswith("ss"):
        return word[:-1]
    return word
