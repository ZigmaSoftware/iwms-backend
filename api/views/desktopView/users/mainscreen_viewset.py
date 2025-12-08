from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.response import Response

from api.apps.mainscreen import MainScreen
from api.serializers.desktopView.users.mainscreen_serializer import MainScreenSerializer


class MainScreenViewSet(viewsets.ModelViewSet):
    serializer_class = MainScreenSerializer
    queryset = MainScreen.objects.filter(is_deleted=False)
    lookup_field = "unique_id"

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter: ?mainscreen_name=xxx
        name_param = self.request.query_params.get("mainscreen_name")
        if name_param:
            queryset = queryset.filter(mainscreen_name__icontains=name_param)

        # Filter: ?mainscreentype_id=MSCRTYPE-000001
        type_param = self.request.query_params.get("mainscreentype_id")
        if type_param:
            queryset = queryset.filter(mainscreentype_id=type_param)

        # Filter: ?icon_name=xxx
        icon_param = self.request.query_params.get("icon_name")
        if icon_param:
            queryset = queryset.filter(icon_name__icontains=icon_param)

        return queryset

    def get_object(self):
        lookup_field = self.lookup_field
        lookup_url_kwarg = self.lookup_url_kwarg or lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)

        queryset = self.filter_queryset(self.get_queryset())
        obj = get_object_or_404(queryset, **{lookup_field: lookup_value})

        self.check_object_permissions(self.request, obj)
        return obj

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.is_deleted = True
        instance.save(update_fields=["is_active", "is_deleted"])

        return Response(
            {"message": "Main Screen deleted successfully"},
            status=status.HTTP_200_OK
        )
