from rest_framework import serializers
from api.apps.userscreenaction import UserScreenAction


class UserScreenActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserScreenAction
        fields = "__all__"
