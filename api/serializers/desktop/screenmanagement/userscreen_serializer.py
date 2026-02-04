from rest_framework import serializers
from api.serializers.utils.tenancy import TenancyReadSerializerMixin
from api.models.screenmanagement.userscreen import UserScreen


class UserScreenSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    mainscreen_name = serializers.CharField(
        source="mainscreen_id.mainscreen_name",
        read_only=True
    )
    mainscreentype_id = serializers.CharField(
        source="mainscreen_id.mainscreentype_id.unique_id",
        read_only=True
    )
    mainscreentype_name = serializers.CharField(
        source="mainscreen_id.mainscreentype_id.type_name",
        read_only=True
    )

    class Meta:
        model = UserScreen
        fields = "__all__"
