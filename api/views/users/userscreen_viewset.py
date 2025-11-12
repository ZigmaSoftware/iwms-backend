from rest_framework import viewsets, status
from rest_framework.response import Response
from ...apps.userscreen import UserScreen
from ...serializers.users.userscreen_serializer import UserScreenSerializer

class UserScreenViewSet(viewsets.ModelViewSet):
    serializer_class = UserScreenSerializer
    queryset = UserScreen.objects.filter(is_delete=False).select_related("mainscreen")

    def get_queryset(self):
        queryset = super().get_queryset()
        mainscreen_param = self.request.query_params.get("mainscreen") or self.request.query_params.get("main_screen")
        if mainscreen_param:
            queryset = queryset.filter(mainscreen_id=mainscreen_param)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.is_delete = True
        instance.save(update_fields=["is_active", "is_delete"])
        return Response({"message": "Screen deleted successfully"}, status=status.HTTP_200_OK)
