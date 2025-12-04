from django.shortcuts import get_object_or_404

from rest_framework import viewsets, status
from rest_framework.response import Response
from api.apps.userscreen import UserScreen
from api.serializers.desktopView.users.userscreen_serializer import UserScreenSerializer


class UserScreenViewSet(viewsets.ModelViewSet):
    serializer_class = UserScreenSerializer
    queryset = UserScreen.objects.filter(is_delete=False).select_related("mainscreen")
    lookup_field = "unique_id"

    def get_queryset(self):
        queryset = super().get_queryset()
        mainscreen_param = self.request.query_params.get("mainscreen") or self.request.query_params.get("main_screen")
        if mainscreen_param:
            queryset = queryset.filter(mainscreen_id=mainscreen_param)
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
        instance.is_delete = True
        instance.save(update_fields=["is_active", "is_delete"])
        return Response({"message": "Screen deleted successfully"}, status=status.HTTP_200_OK)
