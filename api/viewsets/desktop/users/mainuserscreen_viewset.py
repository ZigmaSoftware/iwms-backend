from rest_framework import viewsets
from api.viewsets.superadminmasters.tenant_viewset import TenantModelViewSet
from api.models.users.mainuserscreen import MainUserScreen
from api.serializers.desktop.users.mainuserscreen_serializer import MainUserScreenSerializer

class MainUserScreenViewSet(TenantModelViewSet):
    queryset = MainUserScreen.objects.filter(is_active=True)
    serializer_class = MainUserScreenSerializer
