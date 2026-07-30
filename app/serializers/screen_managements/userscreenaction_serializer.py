from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.screen_managements.userscreenaction import UserScreenAction


class UserScreenActionSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = UserScreenAction
        fields = "__all__"

    def validate_action_name(self, value):
        if str(value or "").strip().lower() == "show":
            raise serializers.ValidationError("The show action is not used in IWMS.")
        return value

    def validate_variable_name(self, value):
        if str(value or "").strip().lower() == "show":
            raise serializers.ValidationError("The show action is not used in IWMS.")
        return value
