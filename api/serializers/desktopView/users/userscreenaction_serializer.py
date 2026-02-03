from rest_framework import serializers
from api.serializers.utils.tenancy import TenancyReadSerializerMixin
from api.apps.userscreenaction import UserScreenAction


class UserScreenActionSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = UserScreenAction
        fields = "__all__"
