from rest_framework import status, viewsets
from rest_framework.response import Response

from api.apps.continent import Continent
from api.serializers.desktopView.masters.continent_serializer import ContinentSerializer

from api.utils.audit_logger import create_audit_log


class ContinentViewSet(viewsets.ModelViewSet):
    queryset = Continent.objects.filter(is_deleted=False)
    serializer_class = ContinentSerializer
    lookup_field = "unique_id"

    # ---------------------------------------------------------
    # CRUD with audit payload
    # ---------------------------------------------------------
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        return Response(
            {
                "continent": serializer.data,
                "audit_log": self._audit_payload(success=True),
            },
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(
            {
                "continent": serializer.data,
                "audit_log": self._audit_payload(success=True),
            }
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)

        return Response(
            {
                "detail": "Continent deleted successfully",
                "audit_log": self._audit_payload(success=True),
            },
            status=status.HTTP_200_OK,
        )

    # ---------------------------------------------------------
    # Base operations
    # ---------------------------------------------------------
    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        instance.delete()

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def _audit_payload(self, *, success, reason=None):
        audit_result = create_audit_log(
            self.request,
            self.request.resolver_match.func,
            success=success,
            reason=reason,
        )

        if not audit_result:
            return {"logged": False}

        return {"logged": True, **audit_result}
