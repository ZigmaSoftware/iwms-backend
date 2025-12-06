from rest_framework import serializers
from api.apps.mainscreentype import MainScreenType


class MainScreenTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MainScreenType
        fields = "__all__"
