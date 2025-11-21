from rest_framework import serializers
from api.apps.userType import UserType


class LoginSerializer(serializers.Serializer):
    user_type = serializers.ChoiceField(choices=[], help_text="Select the User Type")
    username = serializers.CharField(required=True, help_text="Customer username (contact number or name).")
    password = serializers.CharField(write_only=True, required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dynamically load active user types from DB
        user_types = UserType.objects.filter(is_active=True, is_delete=False)

        # Assign dropdown values → (value sent, text shown)
        self.fields['user_type'].choices = [
            (ut.unique_id, ut.name) for ut in user_types
        ]

    def validate(self, attrs):
        attrs["user_type"] = attrs["user_type"].strip()
        attrs["username"] = attrs["username"].strip()

        if not attrs["user_type"]:
            raise serializers.ValidationError({"user_type": "User type is required."})
        if not attrs["username"]:
            raise serializers.ValidationError({"username": "Username is required."})

        return attrs
