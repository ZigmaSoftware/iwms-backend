from rest_framework import viewsets
from api.apps.staffUserType import StaffUserType
from api.serializers.desktopView.users.staffusertype_serializer import StaffUserTypeSerializer


class StaffUserTypeViewSet(viewsets.ModelViewSet):
    queryset = StaffUserType.objects.filter(is_delete=False)
    serializer_class = StaffUserTypeSerializer
