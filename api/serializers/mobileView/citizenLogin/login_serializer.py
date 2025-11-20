from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    user_type = serializers.CharField(required=True, help_text="Supply the UserType name or ID.")
    username = serializers.CharField(required=True, help_text="Customer username (contact number or name).")
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        attrs["user_type"] = attrs["user_type"].strip()
        attrs["username"] = attrs["username"].strip()

        if not attrs["user_type"]:
            raise serializers.ValidationError({"user_type": "User type is required."})
        if not attrs["username"]:
            raise serializers.ValidationError({"username": "Username is required."})

        return attrs
