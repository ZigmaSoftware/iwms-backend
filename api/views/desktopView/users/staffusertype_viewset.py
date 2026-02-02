from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from api.views.tenant_viewset import TenantModelViewSet
from api.apps.staffUserType import StaffUserType
from api.serializers.desktopView.users.staffusertype_serializer import StaffUserTypeSerializer


class StaffUserTypeViewSet(TenantModelViewSet):
    queryset = StaffUserType.objects.filter(is_deleted=False)
    serializer_class = StaffUserTypeSerializer
    lookup_field = "unique_id"
    permission_resource = "Staffusertypes"

    def perform_destroy(self, instance):
        instance.delete()
