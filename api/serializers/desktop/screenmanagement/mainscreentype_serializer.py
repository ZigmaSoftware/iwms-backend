from rest_framework import serializers
from api.serializers.utils.tenancy import TenancyReadSerializerMixin
from api.models.screenmanagement.mainscreentype import MainScreenType


class MainScreenTypeSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = MainScreenType
        fields = "__all__"
