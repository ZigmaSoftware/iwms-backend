from rest_framework import viewsets
from api.apps.mainuserscreen import MainUserScreen
from api.serializers.desktopView.users.mainuserscreen_serializer import MainUserScreenSerializer

class MainUserScreenViewSet(viewsets.ModelViewSet):
    queryset = MainUserScreen.objects.filter(is_active=True)
    serializer_class = MainUserScreenSerializer
