import logging

from django.db import transaction
from django.db.models import Max
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.apps.route_stop import RouteStop
from api.middleware.module_permission_middleware import _authenticate_request
from api.serializers.desktopView.routes.route_stop_serializer import (
    RouteStopSerializer,
)
from api.services.route_optimization_service import (
    RouteOptimizationError,
    RouteOptimizationService,
)


logger = logging.getLogger(__name__)


class RouteOptimizationView(APIView):
    """
    Optimize a route once and persist sequence_no for template stops.
    """

    def post(self, request, route_id):
        auth_error = _authenticate_request(request)
        if auth_error:
            return auth_error

        role = str(getattr(request, "jwt_payload", {}).get("role", "")).lower()
        if role not in {"admin", "supervisor"}:
            return Response(
                {"detail": "Permission denied."},
                status=status.HTTP_403_FORBIDDEN,
            )

        stops_qs = RouteStop.objects.filter(
            route_id=route_id,
            is_active=True,
            is_deleted=False,
        ).order_by("sequence_no", "id")

        if not stops_qs.exists():
            return Response(
                {"detail": "No active route stops found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        stops = list(stops_qs)
        if len(stops) < 2:
            logger.info("Route %s has <2 stops; skipping optimization.", route_id)
            serializer = RouteStopSerializer(stops, many=True)
            return Response(
                {
                    "route_id": route_id,
                    "optimized": False,
                    "stops": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        service = RouteOptimizationService()
        try:
            ordered_ids = service.optimize_route(route_id)
        except RouteOptimizationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as exc:
            logger.exception("Route optimization failed for %s", route_id)
            return Response(
                {"detail": "Route optimization failed."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        with transaction.atomic():
            max_seq = (
                RouteStop.objects.filter(
                    route_id=route_id,
                    is_deleted=False,
                )
                .aggregate(Max("sequence_no"))
                .get("sequence_no__max")
                or 0
            )
            offset = max_seq + len(ordered_ids) + 10
            for index, stop_id in enumerate(ordered_ids, start=1):
                RouteStop.objects.filter(id=stop_id).update(
                    sequence_no=offset + index
                )
            for index, stop_id in enumerate(ordered_ids, start=1):
                RouteStop.objects.filter(id=stop_id).update(sequence_no=index)

        ordered_stops = (
            RouteStop.objects.filter(id__in=ordered_ids)
            .order_by("sequence_no", "id")
        )
        serializer = RouteStopSerializer(ordered_stops, many=True)
        return Response(
            {
                "route_id": route_id,
                "optimized": True,
                "stops": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
