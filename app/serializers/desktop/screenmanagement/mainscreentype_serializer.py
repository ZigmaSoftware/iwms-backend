from rest_framework import serializers
from app.serializers.utils.tenancy import TenancyReadSerializerMixin
from app.models.screenmanagement.mainscreentype import MainScreenType


class MainScreenTypeSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = MainScreenType
        fields = "__all__"
