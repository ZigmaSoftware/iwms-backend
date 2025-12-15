from rest_framework import serializers
from api.apps.attendance import Recognized
from django.conf import settings
import os


class AttendanceListSerializer(serializers.ModelSerializer):
    captured_image = serializers.SerializerMethodField()

    class Meta:
        model = Recognized
        fields = [
            "id",
            "emp_id",
            "name",
            "recognition_date",
            "recognition_time",
            "latitude",
            "longitude",
            "captured_image",
        ]

    def get_captured_image(self, obj):
        """
        Convert stored Windows / absolute path → public MEDIA URL
        """
        if not obj.captured_image_path:
            return None

        path = str(obj.captured_image_path)

        # Extract filename only
        filename = os.path.basename(path)

        return f"{settings.MEDIA_URL}captured_images/{filename}"
