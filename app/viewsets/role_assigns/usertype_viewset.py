from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from app.viewsets.superadminmasters.tenant_viewset import TenantModelViewSet
from app.models.role_assigns.userType import UserType
from app.serializers.role_assigns.usertype_serializer import UserTypeSerializer


class UserTypeViewSet(TenantModelViewSet):
    queryset = UserType.objects.filter(is_deleted=False)
    serializer_class = UserTypeSerializer
    lookup_field = "unique_id"

    def perform_destroy(self, instance):
        instance.delete()
