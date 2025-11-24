from rest_framework import serializers
from api.apps.usercreation import User
from api.apps.userType import UserType

class UserSerializer(serializers.ModelSerializer):
    user_type = serializers.PrimaryKeyRelatedField(queryset=UserType.objects.all())

    class Meta:
        model = User
        fields = '__all__'
