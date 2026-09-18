"""Attendance face recognition — verify a punch selfie and record it.

Which engine does the comparison is decided by `FACE_RECOGNITION_PROVIDER`
in `.env` (see `app/services/face_recognition/__init__.py`); this viewset
never names one, and the HTTP contract is identical either way — same URL,
same form fields, same response keys — so the mobile app works against both
with no rebuild.

Note the similarity numbers are NOT comparable between providers: CompreFace
reports its own 0-1 confidence (cutoff 0.95) while InsightFace reports cosine
similarity between face vectors (cutoff ~0.5). Each provider owns its own
threshold, and the one actually applied is echoed back as `threshold`.
"""

import os
import re

from django.conf import settings
from django.utils import timezone
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from app.models.staff_creations.attendance import Employee, Recognized
from app.services import face_recognition


def _safe_filename(value: str) -> str:
    value = (value or "").strip()
    value = re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", value)
    return value[:80] if value else "capture"


class RecognizeViewSet(ViewSet):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_description="Recognize staff face and mark attendance (multipart/form-data)",
        manual_parameters=[
            openapi.Parameter(
                "emp_id", openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=True,
                description="staff_unique_id (ST-xxxx)"
            ),
            openapi.Parameter(
                "name", openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=True,
                description="Staff name"
            ),
            openapi.Parameter(
                "captured_image", openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="Captured selfie image"
            ),
            openapi.Parameter(
                "latitude", openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                "longitude", openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=True
            ),
        ],
        consumes=["multipart/form-data"],
        responses={200: openapi.Response("OK"), 400: "Bad Request", 404: "Not Found"},
    )
    def create(self, request):
        staff_unique_id = request.data.get("emp_id")
        name = request.data.get("name")
        target_image = request.FILES.get("captured_image")
        lat = request.data.get("latitude")
        lon = request.data.get("longitude")

        # Validate required fields
        missing = []
        if not staff_unique_id: missing.append("emp_id")
        if not name: missing.append("name")
        if not target_image: missing.append("captured_image")
        if not lat: missing.append("latitude")
        if not lon: missing.append("longitude")

        if missing:
            return Response(
                {"error": "Missing fields", "missing_fields": missing},
                status=400
            )

        # Find registered employee (Employee.staff stores the Staffcreation relation)
        employee = Employee.objects.filter(staff__staff_unique_id=staff_unique_id).first()
        if not employee:
            return Response({"error": "Employee not registered"}, status=404)

        # Resolve source image path (Employee.image_path is a STRING like "emp_image/xxx.jpg")
        source_rel = str(employee.image_path or "")
        if not source_rel:
            return Response({"error": "Source image not found for employee"}, status=400)

        source_path = os.path.join(settings.MEDIA_ROOT, source_rel)
        if not os.path.exists(source_path):
            return Response(
                {"error": f"Source image not found: {source_path}"},
                status=400
            )

        captured_bytes = target_image.read()

        provider = face_recognition.get_provider()
        try:
            result = provider.verify(
                captured_bytes,
                reference_path=source_path,
                reference_embedding=employee.face_embedding,
            )
        except face_recognition.FaceUnavailable as exc:
            # Engine down/misconfigured rather than a bad selfie — 503 so the
            # app tells the user to retry instead of blaming their face. The
            # mobile client also treats this as "save offline and sync later".
            return Response({"error": str(exc)}, status=503)
        except face_recognition.FaceError as exc:
            return Response({"error": str(exc)}, status=400)

        # First punch after moving to an embedding-based provider derives the
        # reference vector from the image already on file; cache it so this
        # only ever happens once per employee.
        if result.derived_embedding and not employee.face_embedding:
            employee.face_embedding = result.derived_embedding
            employee.save(update_fields=["face_embedding"])

        if not result.matched:
            return Response(
                {
                    "error": "Face Similarity Not Matched",
                    "similarity_score": result.score,
                    "threshold": result.threshold,
                    "provider": provider.name,
                },
                status=400
            )

        # Only persist the selfie once it has actually matched, so rejected
        # attempts stop filling MEDIA_ROOT with unusable captures.
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        folder = os.path.join(settings.MEDIA_ROOT, "captured_images")
        os.makedirs(folder, exist_ok=True)

        safe_name = _safe_filename(name)
        filename = f"{safe_name}_{staff_unique_id}_{timestamp}.jpg"
        target_path = os.path.join(folder, filename)
        with open(target_path, "wb") as f:
            f.write(captured_bytes)

        captured_rel = f"captured_images/{filename}"

        # Save recognition (match your model fields)
        now = timezone.localtime()
        today = timezone.localdate()
        last = (
            Recognized.objects
            .filter(staff=employee.staff, recognition_date=today)
            .order_by("-records")
            .first()
        )
        punch_type = "OUT" if last and last.punch_type == "IN" else "IN"

        Recognized.objects.create(
            company_id=employee.staff.company_id,
            project_id=employee.staff.project_id,
            staff=employee.staff,
            emp_id=employee.emp_id,
            emp_id_raw=staff_unique_id,          # keep raw string too
            name=employee.name,
            records=now,                         # your model has records DateTimeField
            captured_image_path=captured_rel,    # CharField -> store relative path STRING (CORRECT)
            similarity_score=result.score,
            latitude=str(lat),
            longitude=str(lon),
            recognition_date=today,
            recognition_time=now.time(),
            punch_type=punch_type,
        )

        return Response(
            {
                "message": "Recognition successful",
                "emp_id": staff_unique_id,
                "name": employee.name,
                "score": result.score,
                "threshold": result.threshold,
                "provider": provider.name,
                "captured_image": f"{settings.MEDIA_URL}{captured_rel}",
                "punch_type": punch_type,
            },
            status=200
        )
