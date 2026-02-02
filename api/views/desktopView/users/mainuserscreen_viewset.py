from rest_framework import viewsets
from api.views.tenant_viewset import TenantModelViewSet
from api.apps.mainuserscreen import MainUserScreen
from api.serializers.desktopView.users.mainuserscreen_serializer import MainUserScreenSerializer

class MainUserScreenViewSet(TenantModelViewSet):
    queryset = MainUserScreen.objects.filter(is_active=True)
    serializer_class = MainUserScreenSerializer
