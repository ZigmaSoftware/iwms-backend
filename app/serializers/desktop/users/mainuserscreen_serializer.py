from rest_framework import serializers
from app.serializers.utils.tenancy import TenancyReadSerializerMixin
from app.models.users.mainuserscreen import MainUserScreen

class MainUserScreenSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = MainUserScreen
        fields = "__all__"
