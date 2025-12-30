import logging
import os

import requests
from django.conf import settings

from api.apps.route_stop import RouteStop


logger = logging.getLogger(__name__)


class RouteOptimizationError(Exception):
    pass


class RouteOptimizationService:
    def __init__(self, api_key=None, base_url=None):
        self.api_key = (
            api_key
            or os.getenv("ORS_API_KEY")
            or getattr(settings, "ORS_API_KEY", None)
        )
        self.base_url = (
            base_url
            or os.getenv("ORS_OPTIMIZATION_URL")
            or "https://api.openrouteservice.org/optimization"
        )

    @staticmethod
    def _select_coordinates(stop):
        if stop.entrance_latitude is not None and stop.entrance_longitude is not None:
            return float(stop.entrance_longitude), float(stop.entrance_latitude)
        return float(stop.longitude), float(stop.latitude)

    def optimize_route(self, route_id):
        stops = list(
            RouteStop.objects.filter(
                route_id=route_id,
                is_active=True,
                is_deleted=False,
            ).order_by("sequence_no", "id")
        )

        if len(stops) < 2:
            logger.info("Optimization skipped for route %s (<2 stops)", route_id)
            return [stop.id for stop in stops]

        if not self.api_key:
            raise RouteOptimizationError("ORS API key is not configured.")

        jobs = []
        for stop in stops:
            lon, lat = self._select_coordinates(stop)
            jobs.append({"id": stop.id, "location": [lon, lat]})

        if len(jobs) < 2:
            return [stop.id for stop in stops]

        vehicle_start = jobs[0]["location"]
        payload = {
            "jobs": jobs,
            "vehicles": [
                {
                    "id": 1,
                    "start": vehicle_start,
                    "end": vehicle_start,
                }
            ],
        }

        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                self.base_url, json=payload, headers=headers, timeout=30
            )
        except requests.RequestException as exc:
            raise RouteOptimizationError(
                "Unable to reach ORS optimization API."
            ) from exc

        if response.status_code >= 400:
            raise RouteOptimizationError(
                f"ORS optimization failed ({response.status_code})."
            )

        data = response.json()
        routes = data.get("routes") or []
        if not routes:
            raise RouteOptimizationError("ORS optimization returned no routes.")

        steps = routes[0].get("steps") or []
        ordered_ids = [
            step.get("id")
            for step in steps
            if step.get("type") == "job" and step.get("id") is not None
        ]

        if not ordered_ids:
            raise RouteOptimizationError("ORS optimization returned empty order.")

        missing_ids = {stop.id for stop in stops} - set(ordered_ids)
        if missing_ids:
            logger.warning(
                "ORS optimization missing %s stops for route %s",
                len(missing_ids),
                route_id,
            )
            ordered_ids.extend(
                [stop.id for stop in stops if stop.id in missing_ids]
            )

        return ordered_ids