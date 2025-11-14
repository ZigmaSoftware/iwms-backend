from rest_framework import viewsets
from api.apps.userType import UserType
from api.serializers.desktopView.users.usertype_serializer import UserTypeSerializer

class UserTypeViewSet(viewsets.ModelViewSet):
    queryset = UserType.objects.filter(is_delete=False)
    serializer_class = UserTypeSerializer
