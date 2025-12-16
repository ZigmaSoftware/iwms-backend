from rest_framework import serializers
from api.apps.staffcreation import StaffOfficeDetails, StaffPersonalDetails
from api.apps.attendance import Employee

class StaffPersonalSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffPersonalDetails
        fields = [
            "dob", "blood_group", "marital_status", "gender",
            "present_address", "permanent_address"
        ]

class StaffOfficeSerializer(serializers.ModelSerializer):
    personal = StaffPersonalSerializer(
        source="personal_details",
        read_only=True
    )
    photo = serializers.SerializerMethodField()

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

    def get_photo(self, obj):
        """
        Fetch photo from Employee table using staff_unique_id
        """
        emp = Employee.objects.filter(
            emp_id=obj.staff_unique_id
        ).first()

        if emp and emp.image_path:
            # If ImageField
            if hasattr(emp.image_path, "url"):
                return emp.image_path.url
            # If raw path stored
            return str(emp.image_path)

        return None
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
            "dob",
            "blood_group",
            "photo",
        ]

    def update(self, instance, validated_data):
        image_file = validated_data.pop("photo", None)

        # Update StaffOfficeDetails
        instance = super().update(instance, validated_data)

        # Update Employee table image
        if image_file:
            emp = Employee.objects.filter(
                emp_id=instance.staff_unique_id
            ).first()

            if emp:
                emp.image_path = image_file
                emp.save(update_fields=["image_path"])

        return instance
