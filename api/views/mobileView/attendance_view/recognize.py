from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import os, requests, datetime
from api.apps.attendance import Employee, Recognized
from api.apps.utils.image_compress import resize_image

class RecognizeViewSet(ViewSet):

    def create(self, request):
        emp_id_raw = request.data.get("emp_id")
        name = request.data.get("name")
        target_image = request.FILES.get("captured_image")
        lat = request.data.get("latitude")
        lon = request.data.get("longitude")

        if not all([emp_id_raw, name, target_image, lat, lon]):
            return Response({"error": "Missing fields"}, status=400)

        emp_id = ''.join(filter(str.isdigit, emp_id_raw))

        employee = Employee.objects.filter(emp_id=emp_id).first()
        if not employee:
            return Response({"error": "Employee not registered"}, status=404)

        # save captured image
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = os.path.join(settings.MEDIA_ROOT, "captured_images")
        os.makedirs(folder, exist_ok=True)

        filename = f"{name}{emp_id}{timestamp}.jpg"
        filepath = os.path.join(folder, filename)

        with open(filepath, "wb+") as f:
            for chunk in target_image.chunks():
                f.write(chunk)

        # resize
        source_img = employee.image_path
        target_img = filepath

        # CompreFace API call
        url = "http://125.17.238.158:8000/api/v1/verification/verify"
        headers = {"x-api-key": "f20f91a3-f1ac-43e6-9e2f-ea20f7603061"}
        files = {
            "source_image": ("src.jpg", source_img, "image/jpeg"),
            "target_image": ("tgt.jpg", target_img, "image/jpeg"),
        }
        res = requests.post(url, headers=headers, files=files).json()

        try:
            score = res["result"][0]["face_matches"][0]["similarity"]
        except:
            return Response({"error": "Face not detected"}, status=400)

        if score < 0.95:
            return Response({
                "error": "Face Similarity Not Matched",
                "similarity_score": score
            }, status=400)

        now = datetime.datetime.now()
        Recognized.objects.create(
            emp_id=emp_id,
            emp_id_raw=emp_id_raw,
            name=name,
            records=now,
            captured_image_path=filepath,
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
