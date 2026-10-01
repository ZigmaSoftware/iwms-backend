"""Static route audit: every save of a trip plan's route records the route
before and after it, and what changed."""
import pytest

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.superadmin.audits.static_route_audit import StaticRouteAuditLog as Log
from app.services.static_route import (
    PLANT_START_KEY,
    cp_key,
    route_diff,
    save_plan_static_route,
    sync_plan_static_route,
)
# Shared fixtures (fake_routing is autouse there and must be imported to apply here).
from tests.schedule_setup.test_static_route import (  # noqa: F401
    _plan_detour,
    _trip,
    fake_routing,
    plant,
    second_bin,
    second_cp,
    two_stop_plan,
)

API = "/api/v1/audits/static-route-audit/"
DETOURS = "/api/v1/schedule-operations/route-detour-waypoints/"


def _stop(sid, order, lat=13.0, lng=80.0, label=None, type_="collection_point"):
    return {"id": sid, "label": label or sid, "type": type_, "order": order, "latitude": lat, "longitude": lng}


def _route(stops, detours=()):
    return {"stops": list(stops), "detour_waypoints": list(detours), "distance_meters": 0, "duration_seconds": 0}


class TestRouteDiff:
    def test_stops_added_removed_moved_and_reordered(self):
        before = _route([_stop("plant:start", 1, type_="plant"), _stop("cp:A", 2), _stop("cp:B", 3), _stop("cp:C", 4)])
        after = _route([
            _stop("plant:start", 1, type_="plant"), _stop("cp:B", 2), _stop("cp:A", 3, lat=13.5), _stop("cp:D", 4),
        ])
        changes = route_diff(before, after)
        assert [s["id"] for s in changes["stops_added"]] == ["cp:D"]
        assert [s["id"] for s in changes["stops_removed"]] == ["cp:C"]
        assert [s["id"] for s in changes["stops_moved"]] == ["cp:A"]
        assert changes["stops_moved"][0]["from"]["latitude"] == 13.0
        assert changes["stops_reordered"] is True

    def test_detours_added_removed_and_moved_with_leg_names(self):
        stops = [_stop("cp:A", 1, label="Market"), _stop("cp:B", 2, label="School")]
        detour = {"id": "RDW-1", "after_stop_id": "cp:A", "sequence": 1, "latitude": 13.1, "longitude": 80.1}
        before = _route(stops, [detour, {**detour, "id": "RDW-2"}])
        after = _route(stops, [{**detour, "latitude": 13.2}, {**detour, "id": "RDW-3", "after_stop_id": "cp:B"}])
        changes = route_diff(before, after)
        assert [d["id"] for d in changes["detours_added"]] == ["RDW-3"]
        assert changes["detours_added"][0]["leg"] == "School"
        assert [d["id"] for d in changes["detours_removed"]] == ["RDW-2"]
        moved = changes["detours_moved"][0]
        assert (moved["id"], moved["from"]["latitude"], moved["to"]["latitude"]) == ("RDW-1", 13.1, 13.2)

    def test_plant_is_never_reported(self):
        before = _route([_stop("plant:start", 1, type_="plant")])
        changes = route_diff(before, _route([]))
        assert changes["stops_removed"] == [] and changes["stops_reordered"] is False


@pytest.mark.django_db
class TestAuditWrites:
    def test_first_save_is_created_with_no_previous_route(self, two_stop_plan):
        save_plan_static_route(two_stop_plan, trigger=Log.TRIGGER_MANUAL_SAVE)
        row = Log.objects.get()
        assert (row.change_type, row.trigger, row.previous_version, row.new_version) == (
            Log.CHANGE_CREATED, Log.TRIGGER_MANUAL_SAVE, None, 1,
        )
        assert row.previous_route is None
        assert row.new_route["route_geojson"] is not None
        assert row.trip_plan_code == two_stop_plan.display_code

    def test_detour_added_keeps_both_routes_and_affected_trips(self, two_stop_plan):
        save_plan_static_route(two_stop_plan)
        running = _trip(two_stop_plan, status=DailyTripAssignment.STATUS_IN_PROGRESS)
        _plan_detour(two_stop_plan)
        save_plan_static_route(two_stop_plan)

        row = Log.objects.order_by("-id").first()
        assert row.change_type == Log.CHANGE_DETOUR_ADDED
        assert (row.previous_version, row.new_version) == (1, 2)
        assert row.previous_route["detour_waypoints"] == []
        assert len(row.new_route["detour_waypoints"]) == 1
        assert row.affected_trip_ids == [running.unique_id]
        assert row.affected_trip_count == 1

    def test_stop_change_from_the_trip_plan(self, two_stop_plan, second_cp):
        save_plan_static_route(two_stop_plan)
        TripPlanCollectionPoint.objects.filter(collection_point_id=second_cp.unique_id).update(is_active=False)
        sync_plan_static_route(two_stop_plan, trigger=Log.TRIGGER_TRIP_PLAN_EDIT)

        row = Log.objects.order_by("-id").first()
        assert (row.change_type, row.trigger) == (Log.CHANGE_STOPS_CHANGED, Log.TRIGGER_TRIP_PLAN_EDIT)
        assert [s["id"] for s in row.changes["stops_removed"]] == [cp_key(second_cp.unique_id)]

    def test_unchanged_sync_writes_nothing(self, two_stop_plan):
        save_plan_static_route(two_stop_plan)
        sync_plan_static_route(two_stop_plan)
        assert Log.objects.count() == 1


@pytest.mark.django_db
class TestAuditFromTheMap:
    def test_add_move_remove_detour_gives_one_row_each(self, auth_client, two_stop_plan):
        save_plan_static_route(two_stop_plan)
        body = {"trip_plan_id": two_stop_plan.unique_id, "after_stop_id": PLANT_START_KEY,
                "sequence": 1, "latitude": "13.010000", "longitude": "80.210000"}
        created = auth_client.post(DETOURS, body, format="json")
        assert created.status_code == 201, created.content
        detour_id = created.json()["unique_id"]

        moved = auth_client.patch(f"{DETOURS}{detour_id}/", {"latitude": "13.020000"}, format="json")
        assert moved.status_code == 200, moved.content
        assert auth_client.delete(f"{DETOURS}{detour_id}/").status_code == 204

        rows = list(Log.objects.order_by("id").values_list("change_type", "trigger", "new_version"))
        assert rows == [
            (Log.CHANGE_CREATED, Log.TRIGGER_SYSTEM, 1),
            (Log.CHANGE_DETOUR_ADDED, Log.TRIGGER_DETOUR_EDIT, 2),
            (Log.CHANGE_DETOUR_MOVED, Log.TRIGGER_DETOUR_EDIT, 3),
            (Log.CHANGE_DETOUR_REMOVED, Log.TRIGGER_DETOUR_EDIT, 4),
        ]


@pytest.mark.django_db
class TestAuditApi:
    def test_list_is_light_and_detail_has_both_routes(self, auth_client, two_stop_plan):
        save_plan_static_route(two_stop_plan)
        _plan_detour(two_stop_plan)
        save_plan_static_route(two_stop_plan)

        listing = auth_client.get(API, {"trip_plan_id": two_stop_plan.unique_id})
        assert listing.status_code == 200, listing.content
        rows = listing.json()["results"]
        assert [r["change_type"] for r in rows] == [Log.CHANGE_DETOUR_ADDED, Log.CHANGE_CREATED]
        assert rows[0]["summary"]["detours_added"] == 1
        assert "previous_route" not in rows[0]

        detail = auth_client.get(f"{API}{rows[0]['id']}/").json()
        assert detail["previous_route"]["detour_waypoints"] == []
        assert len(detail["new_route"]["detour_waypoints"]) == 1
        assert len(detail["changes"]["detours_added"]) == 1

    def test_filters_and_options(self, auth_client, two_stop_plan):
        save_plan_static_route(two_stop_plan)
        assert auth_client.get(API, {"change_type": "DETOUR_ADDED"}).json()["count"] == 0
        options = auth_client.get(f"{API}filter-options/").json()
        assert options["trip_plans"] == [{"unique_id": two_stop_plan.unique_id, "name": two_stop_plan.display_code}]
        assert {c["unique_id"] for c in options["change_types"]} >= {Log.CHANGE_CREATED, Log.CHANGE_DETOUR_MOVED}
