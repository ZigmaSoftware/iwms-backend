from app.models.staff_creations.staff_access_configuration import StaffAccessConfiguration

# StaffAccessConfiguration stores each location grant as a comma-separated
# TextField (e.g. `city_ids`), not a real M2M relation — this maps the
# `location_scope_chain`/`location_scope_field` names viewsets already use
# ("cities", "districts", ...) to the model's own `get_<field>_ids()` helper
# that splits the TextField into a list of unique_id strings.
_SCOPE_FIELD_TO_GETTER = {
    "states": "get_state_ids",
    "districts": "get_district_ids",
    "cities": "get_city_ids",
    "zones": "get_zone_ids",
    "panchayats": "get_panchayat_ids",
    "wards": "get_ward_ids",
}


class LocationScopedViewSetMixin:
    """Restrict a location master's queryset (Continent/Country/State/
    District/City/Zone/Panchayat/Ward) to what the requesting staff is
    allowed to see per their StaffAccessConfiguration ("Data Scope" tab).

    Scoping is by ancestor containment, not by matching the target
    record's own id against a static per-record allow-list: a staff
    assigned District X sees every City/Zone/Panchayat/Ward under X,
    including ones created after the assignment was saved — not just
    the specific child records that happened to be individually granted
    at some point. An empty selection at a given level means
    unrestricted at that level (fall through to whatever the level above
    resolved to); the narrowest level with a non-empty grant wins.

    Platform super admins and requests with no resolvable staff record
    (e.g. customer/contractor logins hitting a shared endpoint) are left
    unrestricted — this mixin only narrows the *company-scoped* staff
    path, layering on top of whatever CompanyScopedViewSet.get_queryset()
    already produced for District/City/Zone/Panchayat/Ward.

    `location_scope_chain` lists (StaffAccessConfiguration M2M field name,
    target-model lookup path) pairs ordered narrowest-to-broadest ancestor
    for the target model, e.g. for City:
        [("cities", "unique_id"), ("districts", "district_id__unique_id"),
         ("states", "state_id__unique_id")]
    The mixin filters by the narrowest level that has a non-empty grant.
    For State/Continent/Country (which aren't directly assignable — only
    derived from assigned States) a single-entry chain pointing at the
    "states" grant via the reverse relation is enough.

    `location_scope_field`/`location_scope_lookup` remain as a convenience
    for the common single-level case; if set (and `location_scope_chain`
    is not), they're used to build a one-entry chain.
    """

    location_scope_field = None
    location_scope_lookup = "unique_id"
    location_scope_chain = None

    def _location_scope_is_platform_super_admin(self):
        is_platform_check = getattr(self, "_is_platform_super_admin", None)
        if callable(is_platform_check):
            return is_platform_check()

        user = getattr(self.request, "user", None)
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_superuser", False)
            and getattr(user, "company_id", None) is None
        )

    def _location_scope_chain(self):
        if self.location_scope_chain:
            return self.location_scope_chain
        if self.location_scope_field:
            return [(self.location_scope_field, self.location_scope_lookup)]
        return []

    def _staff_access_configuration(self):
        user = getattr(self.request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return None

        staff_unique_id = getattr(user, "staff_unique_id", None)
        if not staff_unique_id:
            return None

        return (
            StaffAccessConfiguration.objects.filter(
                staff_id=staff_unique_id,
                is_active=True,
                is_deleted=False,
            )
            .first()
        )

    def filter_queryset_by_location_scope(self, queryset):
        if self._location_scope_is_platform_super_admin():
            return queryset

        access_config = self._staff_access_configuration()
        if not access_config:
            return queryset

        for scope_field, lookup in self._location_scope_chain():
            getter_name = _SCOPE_FIELD_TO_GETTER.get(scope_field)
            if not getter_name:
                continue
            scoped_ids = getattr(access_config, getter_name)()
            if not scoped_ids:
                continue

            # Continent/Country aren't directly assignable — only States are
            # — so a "states__<column>" lookup means: resolve the target
            # model's ids from the scoped States' own `<column>` field
            # (State.continent_id / State.country_id), not a real Django
            # relation traversal (State has none to Continent/Country; both
            # are plain string-pseudo-FK CharFields, same as everywhere else
            # in this codebase).
            if lookup.startswith("states__"):
                from app.models.common_masters.state import State
                column = lookup[len("states__"):]
                if column == "unique_id":
                    target_ids = scoped_ids
                else:
                    target_ids = list(
                        State.objects.filter(unique_id__in=scoped_ids)
                        .exclude(**{column: None})
                        .values_list(column, flat=True)
                        .distinct()
                    )
                if not target_ids:
                    continue
                return queryset.filter(unique_id__in=target_ids)

            return queryset.filter(**{f"{lookup}__in": scoped_ids})

        return queryset
