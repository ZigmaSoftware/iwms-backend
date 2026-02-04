from rest_framework import serializers
from api.serializers.utils.tenancy import TenancyReadSerializerMixin
from api.models.users.mainuserscreen import MainUserScreen

class MainUserScreenSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = MainUserScreen
        fields = "__all__"
