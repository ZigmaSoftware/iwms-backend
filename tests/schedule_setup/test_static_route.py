"""A trip plan's static route — drawn, saved, and copied to its daily trips."""
from datetime import date, time, timedelta

import pytest
from django.utils import timezone

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.core_modules.daily_operations.daily_trip_static_route import DailyTripStaticRoute
from app.models.core_modules.daily_operations.route_detour_waypoint import RouteDetourWaypoint
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.core_modules.schedule_setup.trip_plan_static_route import TripPlanStaticRoute
from app.models.masters.plant import Plant
from app.models.masters.waste_masters.bins import Bins
from app.serializers.core_modules.daily_operations.route_detour_waypoint_serializer import (
    RouteDetourWaypointSerializer,
)
from app.services import static_route
from app.services.static_route import (
    PLANT_END_KEY,
    PLANT_START_KEY,
    assignment_static_route,
    cp_key,
    plan_route_stops,
    plan_static_route,
    save_plan_static_route,
    sync_plan_static_route,
)

ROAD = {"type": "FeatureCollection", "features": []}


@pytest.fixture(autouse=True)
def fake_routing(monkeypatch):
    """Stand-in for OpenRouteService; records each routed coordinate list."""
    calls = []

    def route_stops(stops, vehicle_start=None):
        calls.append([vehicle_start, *[stop["location"] for stop in stops]])
        return {"geometry": ROAD, "distance": 1200.0, "duration": 300.0, "vehicle_start": vehicle_start}

    monkeypatch.setattr(static_route, "route_stops", route_stops)
    return calls


@pytest.fixture
def plant(db, company, project):
    return Plant.objects.create(
        company_id=company.unique_id, project_id=project.unique_id,
        name="Main Plant", latitude="13.000000", longitude="80.200000",
    )


@pytest.fixture
def second_cp(db, company, project, state, district, city, panchayat):
    return Collection_point.objects.create(
        cp_name="Second CP",
        company_id=company.unique_id, project_id=project.unique_id,
        state_id=state.unique_id, city_id=city.unique_id, district_id=district.unique_id,
        panchayat_id=panchayat.unique_id,
        latitude="13.0900", longitude="80.2800",
    )


@pytest.fixture
def second_bin(db, company, project, district, city, second_cp, waste_type_obj):
    return Bins.objects.create(
        company_id=company.unique_id, project_id=project.unique_id,
        district_id=district.unique_id, city_id=city.unique_id,
        collection_point_id=second_cp.unique_id,
        wastetype_id=waste_type_obj.unique_id,
        bin_capacity=100, bin_type="small", bin_name="Second Bin", bin_image="", bin_qr="",
    )


@pytest.fixture
def two_stop_plan(db, bin_plan, collection_point, bin_obj, second_cp, second_bin):
    # Plan order is deliberately second_cp first — the route must follow it.
    for sequence, (cp, bin_) in enumerate([(second_cp, second_bin), (collection_point, bin_obj)], start=1):
        TripPlanCollectionPoint.objects.create(
            trip_plan_id=bin_plan.unique_id,
            collection_type=TripPlanCollectionPoint.COLLECTION_TYPE_BIN,
            collection_point_id=cp.unique_id, bin_id=bin_.unique_id,
            sequence=sequence, is_active=True,
        )
    return bin_plan


def _trip(plan, trip_date=None, **fields):
    return DailyTripAssignment.objects.create(
        company_id=plan.company_id, project_id=plan.project_id,
        trip_plan_id=plan.unique_id, trip_date=trip_date or timezone.localdate(), **fields,
    )


def _plan_detour(plan, after_stop_id=PLANT_START_KEY, latitude="13.01", longitude="80.21"):
    return RouteDetourWaypoint.objects.create(
        trip_plan_id=plan.unique_id, after_stop_id=after_stop_id,
        sequence=1, latitude=latitude, longitude=longitude,
    )


@pytest.fixture
def assignment(db, two_stop_plan):
    return _trip(two_stop_plan)


@pytest.mark.django_db
class TestPlanRouteStops:
    def test_follows_plan_sequence_between_plant_visits(self, two_stop_plan, plant, collection_point, second_cp):
        stops = plan_route_stops(two_stop_plan)
        assert [s["id"] for s in stops] == [
            PLANT_START_KEY, cp_key(second_cp.unique_id), cp_key(collection_point.unique_id), PLANT_END_KEY,
        ]
        assert [s["order"] for s in stops] == [1, 2, 3, 4]
        assert stops[1]["details"] == {"Bins": "Second Bin"}

    def test_inactive_plan_stops_are_left_out(self, two_stop_plan, second_cp):
        TripPlanCollectionPoint.objects.filter(collection_point_id=second_cp.unique_id).update(is_active=False)
        ids = [s["id"] for s in plan_route_stops(two_stop_plan)]
        assert cp_key(second_cp.unique_id) not in ids


@pytest.mark.django_db
class TestSavePlanRoute:
    def test_save_stores_stops_detours_and_road_path(self, two_stop_plan, plant, fake_routing):
        _plan_detour(two_stop_plan)
        saved, error, _ = save_plan_static_route(two_stop_plan)
        assert error is None
        assert saved.version == 1
        assert [s["id"] for s in saved.stops] == [s["id"] for s in plan_route_stops(two_stop_plan)]
        assert len(saved.detour_waypoints) == 1
        assert saved.route_geojson == ROAD
        assert saved.distance_meters == 1200.0
        # The detour after the departing plant is routed right after it.
        assert fake_routing[-1][:2] == [[80.2, 13.0], [80.21, 13.01]]

    def test_resave_bumps_version(self, two_stop_plan):
        save_plan_static_route(two_stop_plan)
        saved, _, _ = save_plan_static_route(two_stop_plan)
        assert saved.version == 2
        assert TripPlanStaticRoute.objects.filter(trip_plan_id=two_stop_plan.unique_id).count() == 1

    def test_routing_failure_still_saves_the_route(self, two_stop_plan, monkeypatch):
        def failing(stops, vehicle_start=None):
            raise static_route.OpenRouteServiceError("ORS down")

        monkeypatch.setattr(static_route, "route_stops", failing)
        saved, error, _ = save_plan_static_route(two_stop_plan)
        assert error == "ORS down"
        assert saved.route_geojson is None
        assert len(saved.stops) == 2

    def test_unsaved_changes_flag_tracks_the_drawing(self, two_stop_plan):
        assert plan_static_route(two_stop_plan)["has_unsaved_changes"] is True
        save_plan_static_route(two_stop_plan)
        payload = plan_static_route(two_stop_plan)
        assert payload["has_unsaved_changes"] is False
        assert payload["route_geojson"] == ROAD

        _plan_detour(two_stop_plan)
        payload = plan_static_route(two_stop_plan)
        assert payload["has_unsaved_changes"] is True
        assert payload["route_geojson"] is None


@pytest.mark.django_db
class TestDailyTripCopy:
    def test_new_trip_gets_a_copy_of_the_saved_route(self, two_stop_plan):
        save_plan_static_route(two_stop_plan)
        trip = _trip(two_stop_plan)
        copy = DailyTripStaticRoute.objects.get(trip_assignment_id=trip.unique_id)
        assert copy.plan_route_version == 1
        assert copy.route_geojson == ROAD

    def test_resave_updates_unfinished_trips_but_not_completed_or_past_ones(self, two_stop_plan):
        save_plan_static_route(two_stop_plan)
        scheduled = _trip(two_stop_plan)
        running = _trip(two_stop_plan, status=DailyTripAssignment.STATUS_IN_PROGRESS)
        completed = _trip(two_stop_plan, status=DailyTripAssignment.STATUS_COMPLETED)
        past = _trip(
            two_stop_plan, trip_date=timezone.localdate() - timedelta(days=1),
            status=DailyTripAssignment.STATUS_IN_PROGRESS,
        )

        _, _, updated = save_plan_static_route(two_stop_plan)

        assert updated == 2
        versions = {
            copy.trip_assignment_id: copy.plan_route_version
            for copy in DailyTripStaticRoute.objects.all()
        }
        assert versions == {
            scheduled.unique_id: 2, running.unique_id: 2, completed.unique_id: 1, past.unique_id: 1,
        }

    def test_completed_trip_keeps_its_route_after_the_plan_changes(self, two_stop_plan, second_cp):
        save_plan_static_route(two_stop_plan)
        trip = _trip(two_stop_plan, status=DailyTripAssignment.STATUS_COMPLETED)
        before = [s["id"] for s in assignment_static_route(trip)["stops"]]

        TripPlanCollectionPoint.objects.filter(collection_point_id=second_cp.unique_id).update(is_active=False)
        save_plan_static_route(two_stop_plan)

        assert [s["id"] for s in assignment_static_route(trip)["stops"]] == before


@pytest.mark.django_db
class TestAutomaticSync:
    def test_sync_without_changes_keeps_the_version(self, two_stop_plan):
        save_plan_static_route(two_stop_plan)
        assert sync_plan_static_route(two_stop_plan).version == 1

    def test_sync_after_a_change_saves_and_reaches_running_trips(self, two_stop_plan, second_cp):
        save_plan_static_route(two_stop_plan)
        running = _trip(two_stop_plan, status=DailyTripAssignment.STATUS_IN_PROGRESS)

        TripPlanCollectionPoint.objects.filter(collection_point_id=second_cp.unique_id).update(is_active=False)
        saved = sync_plan_static_route(two_stop_plan)

        assert saved.version == 2
        copy = DailyTripStaticRoute.objects.get(trip_assignment_id=running.unique_id)
        assert copy.plan_route_version == 2
        assert cp_key(second_cp.unique_id) not in [s["id"] for s in copy.stops]

    def test_only_if_saved_leaves_undrawn_plans_alone(self, two_stop_plan):
        assert sync_plan_static_route(two_stop_plan, only_if_saved=True) is None
        assert not TripPlanStaticRoute.objects.filter(trip_plan_id=two_stop_plan.unique_id).exists()

    def test_drawing_a_plan_detour_updates_todays_running_trip(self, auth_client, two_stop_plan):
        save_plan_static_route(two_stop_plan)
        running = _trip(two_stop_plan, status=DailyTripAssignment.STATUS_IN_PROGRESS)

        res = auth_client.post(
            "/api/v1/schedule-operations/route-detour-waypoints/",
            {"trip_plan_id": two_stop_plan.unique_id, "after_stop_id": PLANT_START_KEY,
             "sequence": 1, "latitude": "13.010000", "longitude": "80.210000"},
            format="json",
        )
        assert res.status_code == 201, res.content
        payload = assignment_static_route(running)
        assert payload["plan_route_version"] == 2
        assert len(payload["detour_waypoints"]) == 1

        res = auth_client.delete(f"/api/v1/schedule-operations/route-detour-waypoints/{res.json()['unique_id']}/")
        assert res.status_code == 204, res.content
        payload = assignment_static_route(running)
        assert payload["plan_route_version"] == 3
        assert payload["detour_waypoints"] == []

    def test_detours_cannot_be_drawn_on_a_daily_trip(self, auth_client, assignment):
        res = auth_client.post(
            "/api/v1/schedule-operations/route-detour-waypoints/",
            {"trip_assignment_id": assignment.unique_id, "after_stop_id": PLANT_START_KEY,
             "sequence": 1, "latitude": "13.010000", "longitude": "80.210000"},
            format="json",
        )
        assert res.status_code == 400


@pytest.mark.django_db
class TestAssignmentStaticRoute:
    def test_saved_copy_is_used_with_the_day_status(self, assignment, two_stop_plan, plant):
        save_plan_static_route(two_stop_plan)
        payload = assignment_static_route(assignment)
        assert payload["route_source"] == "saved"
        assert payload["plan_route_version"] == 1
        assert [s["id"] for s in payload["stops"]] == [s["id"] for s in plan_route_stops(two_stop_plan)]
        assert payload["stops"][1]["details"] == {"Bins": "Second Bin (Pending)"}
        assert payload["route_geojson"] == ROAD

    def test_without_a_saved_route_the_trip_follows_the_plan_drawing(self, assignment, two_stop_plan):
        payload = assignment_static_route(assignment)
        assert payload["route_source"] == "plan"
        assert [s["id"] for s in payload["stops"]] == [s["id"] for s in plan_route_stops(two_stop_plan)]
        assert payload["route_geojson"] is None

    def test_route_keeps_plan_order_even_if_daily_sequence_changed(self, assignment, two_stop_plan, collection_point):
        save_plan_static_route(two_stop_plan)
        # e.g. after optimize-route rewrote the day's sequence.
        DailyTripCollectionPoint.objects.filter(
            trip_assignment_id=assignment.unique_id, collection_point_id=collection_point.unique_id,
        ).update(sequence=0)
        assert [s["id"] for s in assignment_static_route(assignment)["stops"]] == [
            s["id"] for s in plan_route_stops(two_stop_plan)
        ]

    def test_plan_stop_missing_from_the_day_is_marked_not_scheduled(self, assignment, second_cp):
        DailyTripCollectionPoint.objects.filter(
            trip_assignment_id=assignment.unique_id, collection_point_id=second_cp.unique_id,
        ).delete()
        stops = assignment_static_route(assignment)["stops"]
        stop = next(s for s in stops if s["id"] == cp_key(second_cp.unique_id))
        assert stop["details"]["Status"] == "Not scheduled"

    def test_trip_without_a_plan_uses_its_own_daily_stops(self, company, project, collection_point, bin_obj):
        trip = DailyTripAssignment.objects.create(
            company_id=company.unique_id, project_id=project.unique_id,
            trip_date=date(2026, 10, 1), scheduled_time=time(6, 0),
        )
        DailyTripCollectionPoint.objects.create(
            trip_assignment_id=trip.unique_id, collection_point_id=collection_point.unique_id,
            bin_id=bin_obj.unique_id, sequence=1,
        )
        payload = assignment_static_route(trip)
        assert payload["route_source"] == "trip"
        assert [s["id"] for s in payload["stops"]] == [cp_key(collection_point.unique_id)]


@pytest.mark.django_db
class TestDetourWaypoints:
    def test_daily_trip_shows_only_the_plans_detours(self, assignment, two_stop_plan):
        _plan_detour(two_stop_plan)
        # A legacy per-trip detour is no longer shown.
        RouteDetourWaypoint.objects.create(
            trip_assignment_id=assignment.unique_id, after_stop_id=PLANT_START_KEY,
            sequence=1, latitude="13.02", longitude="80.22",
        )
        waypoints = assignment_static_route(assignment)["detour_waypoints"]
        assert [w["latitude"] for w in waypoints] == [13.01]

    def test_plan_detour_saved_with_a_bare_collection_point_id_maps_to_its_stop(self, two_stop_plan, second_cp):
        _plan_detour(two_stop_plan, after_stop_id=second_cp.unique_id)
        waypoints = plan_static_route(two_stop_plan)["detour_waypoints"]
        assert [w["after_stop_id"] for w in waypoints] == [cp_key(second_cp.unique_id)]

    def test_serializer_accepts_plan_detours_only(self, assignment, two_stop_plan):
        base = {"after_stop_id": PLANT_START_KEY, "sequence": 1, "latitude": "13.01", "longitude": "80.21"}
        assert RouteDetourWaypointSerializer(data={**base, "trip_plan_id": two_stop_plan.unique_id}).is_valid()
        assert not RouteDetourWaypointSerializer(data={**base, "trip_assignment_id": assignment.unique_id}).is_valid()
        assert not RouteDetourWaypointSerializer(data=base).is_valid()


@pytest.mark.django_db
class TestStaticRouteEndpoints:
    def test_save_then_read_plan_and_daily_routes(self, auth_client, two_stop_plan, plant):
        _plan_detour(two_stop_plan)
        res = auth_client.post(
            "/api/v1/schedule-operations/trip-plan-static-routes/",
            {"trip_plan_id": two_stop_plan.unique_id}, format="json",
        )
        assert res.status_code == 201, res.content
        assert res.json()["version"] == 1

        plan_body = auth_client.get(
            f"/api/v1/schedule-setup/trip-plans/{two_stop_plan.unique_id}/static-route/"
        ).json()
        assert plan_body["has_unsaved_changes"] is False
        assert plan_body["saved"]["version"] == 1
        assert len(plan_body["detour_waypoints"]) == 1

        trip = _trip(two_stop_plan)
        res = auth_client.get(
            "/api/v1/schedule-operations/daily-trip-collection-points/static-route/",
            {"trip_assignment_id": trip.unique_id},
        )
        assert res.status_code == 200, res.content
        body = res.json()
        assert body["route_source"] == "saved"
        assert [s["id"] for s in body["stops"]] == [s["id"] for s in plan_body["stops"]]

    def test_save_requires_a_known_trip_plan(self, auth_client):
        res = auth_client.post(
            "/api/v1/schedule-operations/trip-plan-static-routes/",
            {"trip_plan_id": "TP-missing"}, format="json",
        )
        assert res.status_code == 404
