from app.models.user_creations.staff_access_configuration import StaffAccessConfiguration


class LocationScopedViewSetMixin:
    """Restrict a location master's queryset (Continent/Country/State/
    District/City/Zone/Panchayat/Ward) to what the requesting staff is
    allowed to see per their StaffAccessConfiguration ("Data Scope" tab),
    same convention used at login: an empty selection at a given level
    means unrestricted (every record under whatever the level above
    resolved to), while an explicit selection restricts to just those
    records.

    Platform super admins and requests with no resolvable staff record
    (e.g. customer/contractor logins hitting a shared endpoint) are left
    unrestricted — this mixin only narrows the *company-scoped* staff
    path, layering on top of whatever CompanyScopedViewSet.get_queryset()
    already produced for District/City/Zone/Panchayat/Ward.

    `location_scope_field` names the M2M accessor on
    StaffAccessConfiguration (e.g. "states", "districts") and is also used
    as the FK lookup name on the target model (e.g. state_id__unique_id
    for models whose FK field is `state_id`, or the model's own unique_id
    for State/Continent/Country themselves — see `location_scope_lookup`
    below for the exact field to filter on).
    """

    location_scope_field = None
    location_scope_lookup = "unique_id"

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

    def _staff_access_configuration(self):
        user = getattr(self.request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return None

        staff_unique_id = getattr(user, "staff_unique_id", None)
        if not staff_unique_id:
            return None

        return (
            StaffAccessConfiguration.objects.filter(
                staff_id_id=staff_unique_id,
                is_active=True,
                is_deleted=False,
            )
            .prefetch_related(self.location_scope_field)
            .first()
        )

    def filter_queryset_by_location_scope(self, queryset):
        if self._location_scope_is_platform_super_admin():
            return queryset

        access_config = self._staff_access_configuration()
        if not access_config:
            return queryset

        scoped = getattr(access_config, self.location_scope_field).all()
        if not scoped.exists():
            return queryset

        scoped_ids = list(scoped.values_list("unique_id", flat=True))
        return queryset.filter(**{f"{self.location_scope_lookup}__in": scoped_ids})
