from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import os, requests, datetime
from api.apps.attendance import Employee, Recognized


class RecognizeViewSet(ViewSet):

    def _resolve_path(self, image_field):
        """
        Handles:
        1) ImageFieldFile
        2) Relative path string (emp_image/xxx.jpg)
        3) Absolute path (fallback)
        """
        # ImageField
        if hasattr(image_field, "path"):
            return image_field.path

        # String path
        path = str(image_field)

        # Already absolute
        if os.path.isabs(path):
            return path

        # Relative → MEDIA_ROOT
        return os.path.join(settings.MEDIA_ROOT, path)

    def create(self, request):
        staff_unique_id = request.data.get("emp_id")  # DO NOT strip
        name = request.data.get("name")
        target_image = request.FILES.get("captured_image")
        lat = request.data.get("latitude")
        lon = request.data.get("longitude")

        if not all([staff_unique_id, name, target_image, lat, lon]):
            return Response({"error": "Missing fields"}, status=400)

        # Correct lookup
        employee = Employee.objects.filter(emp_id=staff_unique_id).first()
        if not employee:
            return Response({"error": "Employee not registered"}, status=404)

        # Save captured image
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = os.path.join(settings.MEDIA_ROOT, "captured_images")
        os.makedirs(folder, exist_ok=True)

        filename = f"{staff_unique_id}_{timestamp}.jpg"
        target_path = os.path.join(folder, filename)

        with open(target_path, "wb+") as f:
            for chunk in target_image.chunks():
                f.write(chunk)

        # Resolve source image path
        source_path = self._resolve_path(employee.image_path)

        if not os.path.exists(source_path):
            return Response(
                {"error": f"Source image not found: {source_path}"},
                status=400
            )

        # CompreFace API
        url = "http://125.17.238.158:8000/api/v1/verification/verify"
        headers = {"x-api-key": "c4bb2855-e789-45e4-8dcd-903f03e03f2f"}

        with open(source_path, "rb") as src, open(target_path, "rb") as tgt:
            files = {
                "source_image": ("source.jpg", src, "image/jpeg"),
                "target_image": ("target.jpg", tgt, "image/jpeg"),
            }

            response = requests.post(url, headers=headers, files=files)
            res = response.json()

        # Parse similarity
        try:
            score = res["result"][0]["face_matches"][0]["similarity"]
        except Exception:
            return Response(
                {"error": "Face not detected", "raw": res},
                status=400
            )

        if score < 0.95:
            return Response(
                {
                    "error": "Face Similarity Not Matched",
                    "similarity_score": score
                },
                status=400
            )

        # Save recognition
        now = datetime.datetime.now()
        Recognized.objects.create(
            emp_id=staff_unique_id,
            emp_id_raw=staff_unique_id,
            name=name,
            records=now,
            captured_image_path=target_path,
            similarity_score=score,
            latitude=lat,
            longitude=lon,
            recognition_date=now.date(),
            recognition_time=now.time()
        )

        return Response({
            "message": "Recognition successful",
            "score": score,
            "captured_image": filename
        })
