from rest_framework import serializers
from api.apps.staffcreation import StaffOfficeDetails, StaffPersonalDetails

class StaffPersonalSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffPersonalDetails
        fields = [
            "dob", "blood_group", "marital_status", "gender",
            "present_address", "permanent_address", 
        ]


class StaffOfficeSerializer(serializers.ModelSerializer):
    personal = StaffPersonalSerializer(source="personal_details", read_only=True)

    class Meta:
        model = StaffOfficeDetails
        fields = [
            "id",
            "staff_unique_id",
            "employee_name",
            "department",
            "designation",
            "site_name",
            "doj",
            "photo",
            "personal"
        ]


class StaffUpdateSerializer(serializers.ModelSerializer):
    dob = serializers.DateField(required=False)
    blood_group = serializers.CharField(required=False)
    photo = serializers.ImageField(required=False)

    class Meta:
        model = StaffOfficeDetails
        fields = [
            "employee_name",
            "department",
            "designation",
            "site_name",
            "photo",
            "dob",
            "blood_group"
        ]
