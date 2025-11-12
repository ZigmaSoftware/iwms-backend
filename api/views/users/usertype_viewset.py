from rest_framework import viewsets
from ...apps.userType import UserType
from ...serializers.users.usertype_serializer import UserTypeSerializer

class UserTypeViewSet(viewsets.ModelViewSet):
    queryset = UserType.objects.filter(is_delete=False)
    serializer_class = UserTypeSerializer
