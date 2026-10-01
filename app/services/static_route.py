"""Static Route Map projections.

A static route belongs to a TripPlan: the plan's stops in `sequence` order,
starting and ending at the project's plant, plus any detour waypoints drawn
on the plan. Routes are edited on the trip plan only: every
DailyTripAssignment generated from the plan shows that same route,
read-only, with the day's collection status laid over each stop.

Stops are identified by a location key rather than a row id, so a detour
drawn against the plan lands on the same leg in every daily trip:

- ``cp:<collection_point_id>`` for a bin collection point (all of its bins
  collapse into one stop),
- ``cust:<customer_id>`` for a household / bulk customer,
- ``plant:start`` / ``plant:end`` for the project's plant at either end.

The plan's route — stops, detours and the road path from OpenRouteService —
is stored as a TripPlanStaticRoute, re-saved automatically whenever the
plan's detours or stops change. Each daily trip gets its own copy
(DailyTripStaticRoute) when it is created, and every re-save is copied to
the plan's trips from today on that haven't finished (Scheduled or In
Progress). Completed and past trips keep the route they ran with.
Collection status is never stored; it is always read live.

Nothing here creates daily stop rows.
"""

import math

from django.db import transaction
from django.utils import timezone

from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.core_modules.daily_operations.daily_trip_static_route import DailyTripStaticRoute
from app.models.core_modules.daily_operations.route_detour_waypoint import RouteDetourWaypoint
from app.models.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.core_modules.schedule_setup.trip_plan_static_route import TripPlanStaticRoute
from app.services.openroute_service import OpenRouteServiceError, route_stops

PLANT_START_KEY = "plant:start"
PLANT_END_KEY = "plant:end"


def cp_key(collection_point_id):
    return f"cp:{collection_point_id}"


def customer_key(customer_id):
    return f"cust:{customer_id}"


def _location(obj):
    """(latitude, longitude) as floats, or None when missing or unusable.
    Customer coordinates are free-text columns, so blanks and "NaN" occur."""
    if not obj:
        return None
    try:
        latitude, longitude = float(obj.latitude), float(obj.longitude)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(latitude) and math.isfinite(longitude)):
        return None
    return latitude, longitude


def _plant_for(project_id):
    from app.models.masters.plant import Plant

    if not project_id:
        return None
    return Plant.objects.filter(project_id=project_id, is_active=True, is_deleted=False).first()


def _finalize(groups, project_id):
    """Number the stop groups 1..N and wrap them with the plant. The vehicle
    starts its day at the plant and returns there at the end of the trip."""
    route_stops = [
        {
            "id": group["id"],
            "label": group["label"],
            "type": group["type"],
            "latitude": group["latitude"],
            "longitude": group["longitude"],
            "details": group["details"],
        }
        for group in groups
    ]

    plant = _plant_for(project_id)
    if plant:
        plant_stop = {
            "label": plant.name,
            "type": "plant",
            "latitude": float(plant.latitude),
            "longitude": float(plant.longitude),
            "details": {},
        }
        route_stops = [
            {**plant_stop, "id": PLANT_START_KEY},
            *route_stops,
            {**plant_stop, "id": PLANT_END_KEY},
        ]

    return [{**stop, "order": index + 1} for index, stop in enumerate(route_stops)]


def _plan_groups(plan, ward_ids=None):
    """Ordered stop groups for a trip plan's active stops. Household/bulk
    plan stops are expanded to their customers the same way daily
    generation does (see trip_plan_signals._customers_for_household_stop)."""
    from app.signals.trip_plan_signals import _customers_for_household_stop

    if ward_ids is None:
        ward_ids = plan.get_ward_ids()

    plan_stops = TripPlanCollectionPoint.objects.filter(
        trip_plan_id=plan.unique_id,
        collection_type=plan.collection_type,
        is_active=True,
        is_deleted=False,
    ).order_by("sequence")

    groups = {}
    for stop in plan_stops:
        if stop.collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_BIN:
            cp = stop.collection_point
            location = _location(cp)
            if not location:
                continue
            group = groups.setdefault(cp_key(cp.unique_id), {
                "id": cp_key(cp.unique_id),
                "label": cp.cp_name,
                "type": "collection_point",
                "latitude": location[0],
                "longitude": location[1],
                "bin_ids": [],
            })
            if stop.bin_id:
                group["bin_ids"].append(stop.bin_id)
            continue

        customers = _customers_for_household_stop(stop, wards=ward_ids).order_by("unique_id")
        for customer in customers:
            location = _location(customer)
            if not location:
                continue
            groups.setdefault(customer_key(customer.unique_id), {
                "id": customer_key(customer.unique_id),
                "label": customer.customer_name,
                "type": "household",
                "latitude": location[0],
                "longitude": location[1],
                "bin_ids": [],
            })

    # dicts keep insertion order, which is plan sequence order.
    return list(groups.values())


def _bin_label(bin_id):
    from app.models.masters.waste_masters.bins import Bins

    bin_obj = Bins.objects.filter(unique_id=bin_id).first()
    return bin_obj.bin_name if bin_obj else bin_id


def plan_route_stops(plan, ward_ids=None):
    """The trip plan's current static route, as RouteStop dicts. `ward_ids`
    narrows household expansion to a daily trip's wards."""
    groups = _plan_groups(plan, ward_ids=ward_ids)
    for group in groups:
        group["details"] = (
            {"Bins": ", ".join(_bin_label(bin_id) for bin_id in group["bin_ids"])}
            if group["type"] == "collection_point"
            else {}
        )
    return _finalize(groups, plan.project_id)


def _daily_groups(assignment):
    """Ordered stop groups built from the assignment's own daily rows, each
    carrying that day's status. Used on its own for trips without a plan,
    and as the status overlay for trips with one."""
    groups = {}
    bin_stops = (
        DailyTripCollectionPoint.objects
        .filter(trip_assignment_id=assignment.unique_id, is_deleted=False)
        .order_by("sequence")
    )
    for stop in bin_stops:
        cp = stop.collection_point
        location = _location(cp)
        if not location:
            continue
        group = groups.setdefault(cp_key(cp.unique_id), {
            "id": cp_key(cp.unique_id),
            "label": cp.cp_name,
            "type": "collection_point",
            "latitude": location[0],
            "longitude": location[1],
            "bins": [],
        })
        bin_obj = stop.bin
        group["bins"].append(f"{bin_obj.bin_name if bin_obj else stop.bin_id} ({stop.status})")

    household_stops = (
        DailyTripHouseholdCollection.objects
        .filter(trip_assignment_id=assignment.unique_id, is_deleted=False)
        .order_by("sequence")
    )
    for stop in household_stops:
        customer = stop.customer
        location = _location(customer)
        if not location:
            continue
        groups.setdefault(customer_key(customer.unique_id), {
            "id": customer_key(customer.unique_id),
            "label": customer.customer_name,
            "type": "household",
            "latitude": location[0],
            "longitude": location[1],
            "status": stop.status,
        })

    for group in groups.values():
        group["details"] = (
            {"Bins": ", ".join(group["bins"])}
            if group["type"] == "collection_point"
            else {"Status": group.get("status", "")}
        )
    return groups


_KEY_PREFIXES = ("cp:", "cust:", "plant:")


def _stop_key(after_stop_id):
    """Detours saved before stops had location keys hold some row id
    instead: a daily bin row, a daily household row, the plant, or a bare
    collection point / customer id. Map those onto the key of the same
    stop."""
    if after_stop_id.startswith(_KEY_PREFIXES):
        return after_stop_id
    from app.models.core_modules.schedule_setup.collection_point import Collection_point
    from app.models.masters.customer_masters.customercreation import CustomerCreation

    if Collection_point.objects.filter(unique_id=after_stop_id).exists():
        return cp_key(after_stop_id)
    if CustomerCreation.objects.filter(unique_id=after_stop_id).exists():
        return customer_key(after_stop_id)
    bin_stop = DailyTripCollectionPoint.objects.filter(unique_id=after_stop_id).first()
    if bin_stop and bin_stop.collection_point_id:
        return cp_key(bin_stop.collection_point_id)
    household = DailyTripHouseholdCollection.objects.filter(unique_id=after_stop_id).first()
    if household and household.customer_id:
        return customer_key(household.customer_id)
    # Otherwise it was the plant — and only the departing plant has an
    # outgoing leg to detour.
    return PLANT_START_KEY


def _serialize_waypoints(queryset):
    return [
        {
            "id": waypoint.unique_id,
            "after_stop_id": _stop_key(waypoint.after_stop_id),
            "sequence": waypoint.sequence,
            "latitude": float(waypoint.latitude),
            "longitude": float(waypoint.longitude),
        }
        for waypoint in queryset.order_by("after_stop_id", "sequence")
    ]


def plan_detour_waypoints(trip_plan_id):
    if not trip_plan_id:
        return []
    return _serialize_waypoints(
        RouteDetourWaypoint.objects.filter(
            trip_plan_id=trip_plan_id, is_active=True, is_deleted=False,
        ),
    )


# ----------------------------------------------------------------------
# Road geometry
# ----------------------------------------------------------------------

def _routing_points(stops, waypoints):
    """Stops in order with each leg's detours spliced in after the stop the
    leg starts from. Mirrors buildRoutingCoordinates on the frontend."""
    by_stop = {}
    for waypoint in waypoints:
        by_stop.setdefault(waypoint["after_stop_id"], []).append(waypoint)

    points = []
    for stop in sorted(stops, key=lambda s: s["order"]):
        points.append({"id": stop["id"], "location": [stop["longitude"], stop["latitude"]]})
        for waypoint in sorted(by_stop.get(stop["id"], []), key=lambda w: w["sequence"]):
            points.append({"id": waypoint["id"], "location": [waypoint["longitude"], waypoint["latitude"]]})
    return points


def _road_geometry(stops, waypoints):
    """(geometry, distance, duration, error) for the route through `stops`
    and `waypoints`. Geometry is None when routing is unavailable."""
    points = _routing_points(stops, waypoints)
    if len(points) < 2:
        return None, 0, 0, None
    try:
        route = route_stops(points[1:], vehicle_start=points[0]["location"])
    except OpenRouteServiceError as exc:
        return None, 0, 0, str(exc)
    return route["geometry"], route["distance"], route["duration"], None


def _fingerprint(stops, waypoints):
    """What a saved route must still match to count as up to date: stop
    order and positions, and detour positions (not row ids — a dragged
    detour is re-created with a new id)."""
    return (
        [(s["id"], round(s["latitude"], 6), round(s["longitude"], 6)) for s in stops],
        sorted(
            (w["after_stop_id"], w["sequence"], round(w["latitude"], 6), round(w["longitude"], 6))
            for w in waypoints
        ),
    )


# ----------------------------------------------------------------------
# Trip plan route: draft, save, copy to daily trips
# ----------------------------------------------------------------------

def saved_plan_route(trip_plan_id):
    if not trip_plan_id:
        return None
    return TripPlanStaticRoute.objects.filter(
        trip_plan_id=trip_plan_id, is_active=True, is_deleted=False,
    ).first()


def plan_static_route(plan):
    """The plan's route as currently drawn (stops + detours) plus what was
    last saved. The saved road path is included only while it still matches
    the drawing, so the map never shows a stale line."""
    stops = plan_route_stops(plan)
    waypoints = plan_detour_waypoints(plan.unique_id)
    saved = saved_plan_route(plan.unique_id)
    has_unsaved_changes = (
        saved is None
        or _fingerprint(stops, waypoints) != _fingerprint(saved.stops, saved.detour_waypoints)
    )
    return {
        "trip_plan_id": plan.unique_id,
        "display_code": plan.display_code,
        "vehicle_no": getattr(getattr(plan, "vehicle", None), "vehicle_no", None),
        "stops": stops,
        "detour_waypoints": waypoints,
        "saved": (
            {
                "version": saved.version,
                "saved_at": saved.saved_at,
                "distance_meters": saved.distance_meters,
                "duration_seconds": saved.duration_seconds,
            }
            if saved
            else None
        ),
        "has_unsaved_changes": has_unsaved_changes,
        "route_geojson": saved.route_geojson if saved and not has_unsaved_changes else None,
    }


def copy_plan_route_to_assignment(assignment, plan_route=None):
    """Give one daily trip its own copy of its plan's saved route. Returns
    the copy, or None when the plan has no saved route yet (the trip then
    follows the plan's current drawing live)."""
    plan_route = plan_route or saved_plan_route(assignment.trip_plan_id)
    if not plan_route:
        return None
    copy, _ = DailyTripStaticRoute.objects.update_or_create(
        trip_assignment_id=assignment.unique_id,
        defaults={
            "trip_plan_id": plan_route.trip_plan_id,
            "plan_route_version": plan_route.version,
            "stops": plan_route.stops,
            "detour_waypoints": plan_route.detour_waypoints,
            "route_geojson": plan_route.route_geojson,
            "distance_meters": plan_route.distance_meters,
            "duration_seconds": plan_route.duration_seconds,
            "is_active": True,
            "is_deleted": False,
        },
    )
    return copy


def _active_trips(plan):
    """The plan's daily trips from today on that haven't finished —
    Scheduled or In Progress. They follow the plan's route: every save is
    copied to them. Completed, cancelled and past trips keep the route
    they ran with."""
    from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment

    return DailyTripAssignment.objects.filter(
        trip_plan_id=plan.unique_id,
        is_deleted=False,
        status__in=[DailyTripAssignment.STATUS_SCHEDULED, DailyTripAssignment.STATUS_IN_PROGRESS],
        trip_date__gte=timezone.localdate(),
    )


def _copy_to_active_trips(plan, saved):
    """Copy `saved` to the plan's active trips; returns their ids."""
    trip_ids = []
    for assignment in _active_trips(plan):
        copy_plan_route_to_assignment(assignment, saved)
        trip_ids.append(assignment.unique_id)
    return trip_ids


# ----------------------------------------------------------------------
# Route change audit
# ----------------------------------------------------------------------

def _route_snapshot(route):
    """The parts of a saved route an audit row keeps."""
    return {
        "stops": route.stops,
        "detour_waypoints": route.detour_waypoints,
        "route_geojson": route.route_geojson,
        "distance_meters": route.distance_meters,
        "duration_seconds": route.duration_seconds,
    }


def _same_point(a, b):
    return round(a["latitude"], 6) == round(b["latitude"], 6) and round(a["longitude"], 6) == round(
        b["longitude"], 6
    )


def route_diff(previous, new):
    """What changed between two route snapshots (dicts shaped like
    _route_snapshot). The plant at either end is never reported.

    {
      "stops_added":   [{id, label, type, order, latitude, longitude}],
      "stops_removed": [...],
      "stops_moved":   [{id, label, from: {latitude, longitude}, to: {...}}],
      "stops_reordered": bool,
      "detours_added":   [{id, after_stop_id, leg, sequence, latitude, longitude}],
      "detours_removed": [...],
      "detours_moved":   [{id, leg, from: {after_stop_id, leg, latitude, longitude}, to: {...}}],
    }
    """
    def collection_stops(route):
        return [st for st in (route or {}).get("stops", []) if st.get("type") != "plant"]

    def labels(route):
        return {st["id"]: st.get("label") or st["id"] for st in (route or {}).get("stops", [])}

    def stop_row(st):
        return {key: st.get(key) for key in ("id", "label", "type", "order", "latitude", "longitude")}

    old_stops = {st["id"]: st for st in collection_stops(previous)}
    new_stops = {st["id"]: st for st in collection_stops(new)}
    common = [sid for sid in new_stops if sid in old_stops]
    old_order = [st["id"] for st in collection_stops(previous) if st["id"] in new_stops]
    new_order = [st["id"] for st in collection_stops(new) if st["id"] in old_stops]

    old_labels, new_labels = labels(previous), labels(new)

    def detour_row(waypoint, leg_labels):
        return {
            "id": waypoint["id"],
            "after_stop_id": waypoint["after_stop_id"],
            "leg": leg_labels.get(waypoint["after_stop_id"], waypoint["after_stop_id"]),
            "sequence": waypoint.get("sequence"),
            "latitude": waypoint["latitude"],
            "longitude": waypoint["longitude"],
        }

    old_detours = {w["id"]: w for w in (previous or {}).get("detour_waypoints", [])}
    new_detours = {w["id"]: w for w in (new or {}).get("detour_waypoints", [])}

    detours_moved = []
    for wid in new_detours:
        if wid not in old_detours:
            continue
        before, after = old_detours[wid], new_detours[wid]
        if _same_point(before, after) and before["after_stop_id"] == after["after_stop_id"]:
            continue
        before_row, after_row = detour_row(before, old_labels), detour_row(after, new_labels)
        detours_moved.append({
            "id": wid,
            "leg": after_row["leg"],
            "from": {k: before_row[k] for k in ("after_stop_id", "leg", "latitude", "longitude")},
            "to": {k: after_row[k] for k in ("after_stop_id", "leg", "latitude", "longitude")},
        })

    return {
        "stops_added": [stop_row(new_stops[sid]) for sid in new_stops if sid not in old_stops],
        "stops_removed": [stop_row(old_stops[sid]) for sid in old_stops if sid not in new_stops],
        "stops_moved": [
            {
                "id": sid,
                "label": new_stops[sid].get("label"),
                "from": {"latitude": old_stops[sid]["latitude"], "longitude": old_stops[sid]["longitude"]},
                "to": {"latitude": new_stops[sid]["latitude"], "longitude": new_stops[sid]["longitude"]},
            }
            for sid in common
            if not _same_point(old_stops[sid], new_stops[sid])
        ],
        "stops_reordered": old_order != new_order,
        "detours_added": [detour_row(new_detours[w], new_labels) for w in new_detours if w not in old_detours],
        "detours_removed": [detour_row(old_detours[w], old_labels) for w in old_detours if w not in new_detours],
        "detours_moved": detours_moved,
    }


def _change_type(previous, changes):
    from app.models.superadmin.audits.static_route_audit import StaticRouteAuditLog as Log

    if previous is None:
        return Log.CHANGE_CREATED
    if changes["stops_added"] or changes["stops_removed"] or changes["stops_moved"] or changes["stops_reordered"]:
        return Log.CHANGE_STOPS_CHANGED
    kinds = [
        kind
        for kind, key in (
            (Log.CHANGE_DETOUR_ADDED, "detours_added"),
            (Log.CHANGE_DETOUR_REMOVED, "detours_removed"),
            (Log.CHANGE_DETOUR_MOVED, "detours_moved"),
        )
        if changes[key]
    ]
    if not kinds:
        return Log.CHANGE_RESAVED
    return kinds[0] if len(kinds) == 1 else Log.CHANGE_ROUTE_CHANGED


def _write_route_audit(plan, previous, saved, trip_ids, trigger, user_id, routing_error):
    from app.models.superadmin.audits.static_route_audit import StaticRouteAuditLog

    new = _route_snapshot(saved)
    changes = route_diff(previous, new)
    return StaticRouteAuditLog.objects.create(
        company_id=plan.company_id,
        project_id=plan.project_id,
        trip_plan_id=plan.unique_id,
        trip_plan_code=plan.display_code,
        change_type=_change_type(previous, changes),
        trigger=trigger or StaticRouteAuditLog.TRIGGER_SYSTEM,
        previous_version=(saved.version - 1) if previous is not None else None,
        new_version=saved.version,
        previous_route=previous,
        new_route=new,
        changes=changes,
        distance_change_meters=(new["distance_meters"] or 0) - ((previous or {}).get("distance_meters") or 0),
        duration_change_seconds=(new["duration_seconds"] or 0) - ((previous or {}).get("duration_seconds") or 0),
        affected_trip_ids=trip_ids,
        affected_trip_count=len(trip_ids),
        routing_error=(routing_error or "")[:255] or None,
        updated_by=user_id,
    )


def save_plan_static_route(plan, user_id=None, trigger=None):
    """Store the plan's route as currently drawn, with its road path, copy
    it to the plan's active daily trips (see _active_trips), and record the
    change — previous route, new route and what differs — in
    StaticRouteAuditLog. `trigger` is one of StaticRouteAuditLog.TRIGGER_*.
    Returns (saved route, routing error or None, number of trips updated)."""
    stops = plan_route_stops(plan)
    waypoints = plan_detour_waypoints(plan.unique_id)
    # Routed before the transaction: it's an external HTTP call.
    geometry, distance, duration, routing_error = _road_geometry(stops, waypoints)

    with transaction.atomic():
        saved = (
            TripPlanStaticRoute.objects.select_for_update()
            .filter(trip_plan_id=plan.unique_id)
            .first()
        )
        previous = _route_snapshot(saved) if saved else None
        if saved:
            saved.version += 1
            saved.is_active = True
            saved.is_deleted = False
            saved.updated_by_id = user_id
        else:
            saved = TripPlanStaticRoute(trip_plan_id=plan.unique_id, created_by_id=user_id)
        saved.stops = stops
        saved.detour_waypoints = waypoints
        saved.route_geojson = geometry
        saved.distance_meters = distance or 0
        saved.duration_seconds = duration or 0
        saved.saved_at = timezone.now()
        saved.save()
        trip_ids = _copy_to_active_trips(plan, saved)
        _write_route_audit(plan, previous, saved, trip_ids, trigger, user_id, routing_error)

    return saved, routing_error, len(trip_ids)


def sync_plan_static_route(plan, user_id=None, only_if_saved=False, trigger=None):
    """Keep the stored route in step with the plan after it changes (a
    detour drawn or removed, stops edited on the trip plan form), so its
    daily trips pick the change up without a manual save.

    Saves a new version only when the route actually changed; otherwise
    just makes sure every active trip has the current version. With
    `only_if_saved`, does nothing for a plan whose route was never saved.
    Routing failures never block the edit that triggered this. Returns the
    saved route, or None."""
    saved = saved_plan_route(plan.unique_id)
    if not saved and only_if_saved:
        return None
    if saved and _fingerprint(plan_route_stops(plan), plan_detour_waypoints(plan.unique_id)) == _fingerprint(
        saved.stops, saved.detour_waypoints
    ):
        _copy_to_active_trips(plan, saved)
        return saved
    saved, _, _ = save_plan_static_route(plan, user_id=user_id, trigger=trigger)
    return saved


# ----------------------------------------------------------------------
# Daily trip route
# ----------------------------------------------------------------------

def _with_day_status(route_stops, daily):
    """`route_stops` (a planned route) with each stop's details replaced by
    the day's status. Planned stops the day doesn't have are marked "Not
    scheduled"; daily stops the plan doesn't have (added to this day only)
    go after the planned ones, before the return to the plant."""
    daily = dict(daily)
    stops = []
    for stop in sorted(route_stops, key=lambda s: s["order"]):
        if stop["type"] == "plant":
            stops.append(dict(stop))
            continue
        day = daily.pop(stop["id"], None)
        details = day["details"] if day else {**stop.get("details", {}), "Status": "Not scheduled"}
        stops.append({**stop, "details": details})

    extras = [
        {key: group[key] for key in ("id", "label", "type", "latitude", "longitude", "details")}
        for group in daily.values()
    ]
    if stops and stops[-1]["id"] == PLANT_END_KEY:
        stops[-1:-1] = extras
    else:
        stops.extend(extras)
    return [{**stop, "order": index + 1} for index, stop in enumerate(stops)], bool(extras)


def assignment_static_route(assignment):
    """The static route payload for one daily trip:

    - "saved": the trip's own copy of its plan's saved route;
    - "plan": the plan has no saved route yet — follow its current drawing;
    - "trip": no trip plan — the trip's own stops in their own order.

    Read-only: the route is edited on the trip plan. The stored road path
    is returned unless the day has extra stops the plan doesn't (then the
    map re-routes through them).
    """
    daily = _daily_groups(assignment)

    plan = None
    if assignment.trip_plan_id:
        from app.models.core_modules.schedule_setup.trip_plan import TripPlan

        plan = TripPlan.objects.filter(unique_id=assignment.trip_plan_id, is_deleted=False).first()

    copy = DailyTripStaticRoute.objects.filter(
        trip_assignment_id=assignment.unique_id, is_active=True, is_deleted=False,
    ).first()

    geometry = None
    distance = duration = 0
    plan_route_version = None
    if copy:
        source = "saved"
        stops, has_extras = _with_day_status(copy.stops, daily)
        plan_waypoints = copy.detour_waypoints
        plan_route_version = copy.plan_route_version
        if not has_extras:
            geometry = copy.route_geojson
            distance, duration = copy.distance_meters, copy.duration_seconds
    elif plan:
        source = "plan"
        stops, _ = _with_day_status(
            plan_route_stops(plan, ward_ids=assignment.get_ward_ids() or None), daily,
        )
        plan_waypoints = plan_detour_waypoints(plan.unique_id)
    else:
        source = "trip"
        stops = _finalize(list(daily.values()), assignment.project_id)
        plan_waypoints = []

    return {
        "trip_assignment_id": assignment.unique_id,
        "trip_plan_id": assignment.trip_plan_id,
        "trip_date": assignment.trip_date,
        "vehicle_no": getattr(assignment.vehicle, "vehicle_no", None),
        "route_source": source,
        "plan_route_version": plan_route_version,
        "stops": stops,
        "detour_waypoints": plan_waypoints,
        "route_geojson": geometry,
        "distance_meters": distance,
        "duration_seconds": duration,
    }
