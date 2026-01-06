from rest_framework import serializers
from api.apps.userpermission import UserPermission

class UserPermissionSerializer(serializers.ModelSerializer):
    user_type_name = serializers.SerializerMethodField()
    main_screen_name = serializers.SerializerMethodField()
    user_screen_name = serializers.SerializerMethodField()

    class Meta:
        model = UserPermission
        fields = [
            "id",
            "unique_id",
            "user_type",
            "user_type_name",
            "main_screen",
            "main_screen_name",
            "user_screen",
            "user_screen_name",
            "permissions",
            "is_active",
            "is_delete"
        ]

    def get_user_type_name(self, obj):
        return obj.user_type.name if obj.user_type else None

    def get_main_screen_name(self, obj):
        return obj.main_screen.mainscreen if obj.main_screen else None

    def get_user_screen_name(self, obj):
        return obj.user_screen.screen_name if obj.user_screen else None
