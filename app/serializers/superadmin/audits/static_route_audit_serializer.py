from rest_framework import serializers

from app.models.superadmin.audits.static_route_audit import StaticRouteAuditLog
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin_masters.auth_user import User
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class StaticRouteAuditLogSerializer(serializers.ModelSerializer):
    """List view of a static route change: who, when, which plan, what kind
    of change, and counts of what differs. The full route snapshots are left
    out (they carry the road path, ~20 KB each) — see the detail serializer.
    Name lookups are memoised per serializer instance, like the permission
    audit."""

    change_type_label = serializers.CharField(source="get_change_type_display", read_only=True)
    trigger_label = serializers.CharField(source="get_trigger_display", read_only=True)
    company_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    previous_distance_meters = serializers.SerializerMethodField()
    new_distance_meters = serializers.SerializerMethodField()
    previous_duration_seconds = serializers.SerializerMethodField()
    new_duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = StaticRouteAuditLog
        fields = [
            "id",
            "trip_plan_id",
            "trip_plan_code",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "change_type",
            "change_type_label",
            "trigger",
            "trigger_label",
            "previous_version",
            "new_version",
            "summary",
            "previous_distance_meters",
            "new_distance_meters",
            "distance_change_meters",
            "previous_duration_seconds",
            "new_duration_seconds",
            "duration_change_seconds",
            "affected_trip_count",
            "routing_error",
            "updated_by",
            "updated_by_name",
            "timestamp",
        ]
        read_only_fields = fields

    def _lookup(self, model, value, field, name_field):
        if not value:
            return None
        cache = self.__dict__.setdefault("_name_cache", {})
        key = (model, value)
        if key not in cache:
            cache[key] = (
                model.objects.filter(**{field: value})
                .values_list(name_field, flat=True)
                .first()
            )
        return cache[key]

    def get_company_name(self, obj):
        return self._lookup(Company, obj.company_id, "unique_id", "name")

    def get_project_name(self, obj):
        return self._lookup(Project, obj.project_id, "unique_id", "name")

    def get_updated_by_name(self, obj):
        return (
            self._lookup(Staffcreation, obj.updated_by, "staff_unique_id", "employee_name")
            or self._lookup(User, obj.updated_by, "unique_id", "username")
            or obj.updated_by
        )

    def get_summary(self, obj):
        changes = obj.changes or {}
        return {
            "stops_added": len(changes.get("stops_added", [])),
            "stops_removed": len(changes.get("stops_removed", [])),
            "stops_moved": len(changes.get("stops_moved", [])),
            "stops_reordered": bool(changes.get("stops_reordered")),
            "detours_added": len(changes.get("detours_added", [])),
            "detours_removed": len(changes.get("detours_removed", [])),
            "detours_moved": len(changes.get("detours_moved", [])),
        }

    @staticmethod
    def _route_value(route, key):
        return (route or {}).get(key) if route else None

    def get_previous_distance_meters(self, obj):
        return self._route_value(obj.previous_route, "distance_meters")

    def get_new_distance_meters(self, obj):
        return self._route_value(obj.new_route, "distance_meters")

    def get_previous_duration_seconds(self, obj):
        return self._route_value(obj.previous_route, "duration_seconds")

    def get_new_duration_seconds(self, obj):
        return self._route_value(obj.new_route, "duration_seconds")


class StaticRouteAuditLogDetailSerializer(StaticRouteAuditLogSerializer):
    """One change in full: both route snapshots, the itemised changes and
    the daily trips that were moved onto the new route."""

    class Meta(StaticRouteAuditLogSerializer.Meta):
        fields = StaticRouteAuditLogSerializer.Meta.fields + [
            "previous_route",
            "new_route",
            "changes",
            "affected_trip_ids",
        ]
        read_only_fields = fields
