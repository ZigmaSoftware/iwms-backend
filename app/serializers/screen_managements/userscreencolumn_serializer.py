# =========================================================
# serializers/screen_managements/userscreencolumn_serializer.py
# =========================================================

from rest_framework import serializers

from app.models.screen_managements.userscreencolumn import (
    UserScreenColumn
)


class UserScreenColumnSerializer(serializers.ModelSerializer):

    userscreen_name = serializers.CharField(
        source="userscreen_id.userscreen_name",
        read_only=True
    )

    class Meta:

        model = UserScreenColumn

        fields = "__all__"