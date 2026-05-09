from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.role_assigns.userType import UserType
from app.serializers.role_assigns.usertype_serializer import UserTypeSerializer
from app.utils.audit_mixin import AuditViewSetMixin


class UserTypeViewSet(AuditViewSetMixin,CompanyScopedViewSet):
    queryset = UserType.objects.filter(is_deleted=False)
    serializer_class = UserTypeSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "role-assigns"
    AUDIT_ENDPOINT = "user-type"

    def perform_destroy(self, instance):
        instance.delete()
