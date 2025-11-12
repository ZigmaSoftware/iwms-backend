from rest_framework import viewsets, status
from rest_framework.response import Response
from ...apps.userCreation import User
from ...serializers.users.user_serializer import UserSerializer

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter(is_delete=False)
    serializer_class = UserSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_delete = True
        instance.save()
        return Response({"message": "User soft deleted successfully"}, status=status.HTTP_200_OK)
