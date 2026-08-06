from app.models.user_creations.staff_access_configuration import StaffAccessConfiguration


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

        chain = self._location_scope_chain()
        prefetch_fields = [scope_field for scope_field, _ in chain]

        return (
            StaffAccessConfiguration.objects.filter(
                staff_id_id=staff_unique_id,
                is_active=True,
                is_deleted=False,
            )
            .prefetch_related(*prefetch_fields)
            .first()
        )

    def filter_queryset_by_location_scope(self, queryset):
        if self._location_scope_is_platform_super_admin():
            return queryset

        access_config = self._staff_access_configuration()
        if not access_config:
            return queryset

        for scope_field, lookup in self._location_scope_chain():
            scoped = getattr(access_config, scope_field).all()
            if not scoped.exists():
                continue

            scoped_ids = list(scoped.values_list("unique_id", flat=True))
            return queryset.filter(**{f"{lookup}__in": scoped_ids})

        return queryset
