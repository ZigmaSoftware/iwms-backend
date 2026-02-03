from django.shortcuts import get_object_or_404

from rest_framework import viewsets, status
from rest_framework.response import Response
from api.views.tenant_viewset import TenantModelViewSet
from api.apps.staffcreation import StaffOfficeDetails
from api.serializers.desktopView.users.user_serializer import StaffSerializer


class StaffViewSet(TenantModelViewSet):
    queryset = StaffOfficeDetails.objects.filter(is_deleted=False)
    serializer_class = StaffSerializer
    lookup_field = "unique_id"
    permission_resource = "UsersCreation"

    def get_object(self):
        lookup_field = self.lookup_field
        lookup_url_kwarg = self.lookup_url_kwarg or lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        queryset = self.filter_queryset(self.get_queryset())
        obj = get_object_or_404(queryset, **{lookup_field: lookup_value})

        self.check_object_permissions(self.request, obj)
        return obj

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()
        return Response({"message": "Staff soft deleted successfully"}, status=status.HTTP_200_OK)
