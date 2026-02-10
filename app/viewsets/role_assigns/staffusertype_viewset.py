from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.role_assigns.staffUserType import StaffUserType
from app.serializers.role_assigns.staffusertype_serializer import StaffUserTypeSerializer


class StaffUserTypeViewSet(CompanyScopedViewSet):
    queryset = StaffUserType.objects.filter(is_deleted=False)
    serializer_class = StaffUserTypeSerializer
    lookup_field = "unique_id"
    permission_resource = "Staffusertypes"

    def perform_destroy(self, instance):
        instance.delete()
