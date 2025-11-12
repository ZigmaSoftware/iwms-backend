from rest_framework import serializers
from ...apps.userType import UserType

class UserTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserType
        fields = '__all__'
