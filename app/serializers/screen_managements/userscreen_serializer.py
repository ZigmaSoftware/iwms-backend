from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.screen_managements.userscreen import UserScreen


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
