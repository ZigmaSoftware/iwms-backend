from rest_framework import serializers
from api.apps.staffUserType import StaffUserType

class StaffUserTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffUserType
        fields = '__all__'
