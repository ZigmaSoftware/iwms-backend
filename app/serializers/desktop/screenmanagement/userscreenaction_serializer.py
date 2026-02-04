from rest_framework import serializers
from app.serializers.utils.tenancy import TenancyReadSerializerMixin
from app.models.screenmanagement.userscreenaction import UserScreenAction


class UserScreenActionSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = UserScreenAction
        fields = "__all__"
