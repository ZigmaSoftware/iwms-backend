"""Vehicle Status Dashboard — where every vehicle is and what it did today.

GET /api/v1/dashboards/fleet-status/
    ?company_id=  &project_id=   same scoping as the Admin Dashboard
    &date=                       the day looked at; defaults to today

    Every vehicle in scope with its state, current trip, crew, supervisor,
    stops and weight collected that day and month to date.

GET /api/v1/dashboards/fleet-status/<vehicle_id>/
    Same parameters. One vehicle: trips and start timings, crew and
    alternative crew, breakdowns, re-trips, delay reports, stops and weight
    by collection type and waste type. 404 for a vehicle outside the scope.

Granted per staff through the `dashboard / vehicle-status-dashboard` screen.
A supervisor (staff user type named "...supervisor...", the rule of
CompanyScopedViewSet._is_supervisor_user) sees only the vehicles under their
control — see vehicle_status.supervised_vehicles — whatever they request.

The route is "fleet-status", not "vehicle-status": ModulePermissionMiddleware
reads a path segment starting with "v" as the API version and would never
match it to its screen.
"""
from dataclasses import replace

from django.http import Http404
from rest_framework.response import Response

from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.services import vehicle_status
from app.viewsets.dashboard.admin_dashboard_viewset import AdminDashboardViewSet


def supervisor_ids(user):
    """The ids a supervisor's vehicles and trip plans may name them by, or
    None when the user is not a supervisor (sees every vehicle in scope)."""
    if not isinstance(user, Staffcreation):
        return None
    role = getattr(user, "staffusertype", None)
    if "supervisor" not in (getattr(role, "name", "") or "").lower():
        return None
    return tuple(
        i for i in {user.staff_unique_id, getattr(user, "unique_id", None)} if i
    )


class VehicleStatusDashboardViewSet(AdminDashboardViewSet):
    permission_resource = "VehicleStatusDashboard"

    def _day_scope(self, request):
        scope, _, projects, selected, _ = self._scope(request)
        # One day: the end of whatever range was sent (`date` sets both).
        return replace(scope, start=scope.end), projects, selected

    def list(self, request):
        scope, projects, selected = self._day_scope(request)
        supervisor = supervisor_ids(request.user)
        return Response({
            **vehicle_status.fleet_status(scope, supervisor),
            "viewer": {"supervisor_only": supervisor is not None},
            "filters": {
                "projects": [{"id": p.unique_id, "name": p.name} for p in projects],
                "project_ids": [p.unique_id for p in selected],
            },
        })

    def retrieve(self, request, pk=None):
        scope, _, _ = self._day_scope(request)
        vehicle = (
            vehicle_status.vehicles_in_scope(scope, supervisor_ids(request.user))
            .filter(unique_id=pk)
            .first()
        )
        if not vehicle:
            raise Http404("Vehicle not found")
        return Response(vehicle_status.vehicle_status(scope, vehicle))
