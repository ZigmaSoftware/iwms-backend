from rest_framework import serializers
from api.apps.staffUserType import StaffUserType


class StaffUserTypeSerializer(serializers.ModelSerializer):
    # Extra field
    usertype_name = serializers.CharField(
        source="usertype_id.name",
        read_only=True
    )

    class Meta:
        model = StaffUserType
        fields = "__all__"
        read_only_fields = ["unique_id"]
    
    def validate_usertype_id(self, usertype_obj):
        """Only allow StaffUserType if UserType is 'staff'."""

        if usertype_obj.is_deleted:
            raise serializers.ValidationError("Selected UserType is deleted.")

        if not usertype_obj.is_active:
            raise serializers.ValidationError("Selected UserType is inactive.")

        if usertype_obj.name.lower().strip() != "staff":
            raise serializers.ValidationError(
                "Staff User Types can only be mapped to UserType = 'staff'."
            )

        return usertype_obj
