from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from api.views.tenant_viewset import TenantModelViewSet
from api.apps.userType import UserType
from api.serializers.desktopView.users.usertype_serializer import UserTypeSerializer


class UserTypeViewSet(TenantModelViewSet):
    queryset = UserType.objects.filter(is_deleted=False)
    serializer_class = UserTypeSerializer
    lookup_field = "unique_id"

    def perform_destroy(self, instance):
        instance.delete()
