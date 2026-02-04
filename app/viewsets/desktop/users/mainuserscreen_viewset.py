from rest_framework import viewsets
from app.viewsets.superadminmasters.tenant_viewset import TenantModelViewSet
from app.models.users.mainuserscreen import MainUserScreen
from app.serializers.desktop.users.mainuserscreen_serializer import MainUserScreenSerializer

class MainUserScreenViewSet(TenantModelViewSet):
    queryset = MainUserScreen.objects.filter(is_active=True)
    serializer_class = MainUserScreenSerializer
