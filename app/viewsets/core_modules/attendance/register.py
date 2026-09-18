"""Attendance face registration.

Saves a staff member's reference selfie (as an `Employee` row — this
project's holder of the attendance profile, distinct from `Staffcreation`)
and, on providers that compare face vectors, the embedding derived from it.
Which engine validates the photo is decided by `FACE_RECOGNITION_PROVIDER` in
`.env` (see `app/services/face_recognition/__init__.py`); this viewset never
names one.

The HTTP contract is unchanged from the CompreFace-only version — same URL,
same form fields, same response keys — so the mobile app works against either
engine with no rebuild. One real behaviour change: registration now actually
validates the photo (single clear face) before saving, which it never did
before — every other project already applies this at register time, and
accepting an unusable reference photo silently would only surface as
"employee not registered" confusion at the first punch attempt.
"""

import os
from datetime import datetime

from django.conf import settings
from dateutil import parser
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.staff_creations.attendance import Employee
from app.models.staff_creations.staffcreation import Staffcreation
from app.services import face_recognition
from app.utils.qr import generate_qr


def _clean_text(value, fallback=""):
    value = fallback if value is None else value
    return str(value).strip()


class RegisterViewSet(ViewSet):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_description=(
            "Register a staff member's reference face for attendance. Validated "
            "by whichever engine FACE_RECOGNITION_PROVIDER selects."
        ),
        manual_parameters=[
            openapi.Parameter(
                "emp_id", openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=True,
                description="staff_unique_id (ST-xxxx)"
            ),
            openapi.Parameter(
                "source_image", openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True
            ),
            openapi.Parameter(
                "name", openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                "department", openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                "dob", openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                "blood_group", openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False
            ),
        ],
        consumes=["multipart/form-data"],
    )
    def create(self, request):
        emp_id = request.data.get("emp_id")
        source_image = request.FILES.get("source_image")

        if not emp_id or not source_image:
            return Response(
                {"error": "emp_id and source_image required"},
                status=400
            )

        staff = Staffcreation.objects.filter(
            staff_unique_id=emp_id
        ).first()

        if not staff:
            return Response({"error": "Staff not found"}, status=404)

        existing = Employee.objects.filter(
            staff=staff
        ).first()

        if existing:
            # Handle potential binary data in image_path and qr_code_path
            image_value = existing.image_path
            qr_value = existing.qr_code_path

            # If the field contains binary data, convert to empty string
            if isinstance(image_value, (bytes, bytearray, memoryview)):
                image_value = ""
            if isinstance(qr_value, (bytes, bytearray, memoryview)):
                qr_value = ""

            return Response({
                "message": "Employee already registered",
                "emp_id": emp_id,
                "name": existing.name,
                "department": existing.department,
                "image": image_value,
                "qr": qr_value,
            })

        name = _clean_text(
            request.data.get("name"),
            fallback=staff.employee_name or staff.username or emp_id,
        )
        department = _clean_text(
            request.data.get("department"),
            fallback=staff.department or "",
        )

        try:
            dob = (
                parser.parse(request.data.get("dob")).date()
                if request.data.get("dob")
                else None
            )
        except (TypeError, ValueError, OverflowError, parser.ParserError):
            return Response({"error": "Invalid dob"}, status=400)

        blood_group = _clean_text(request.data.get("blood_group"))

        # Read once: the face provider needs the bytes and the file also has
        # to be written to disk, and an UploadedFile stream can only be
        # consumed once.
        image_bytes = source_image.read()

        provider = face_recognition.get_provider()
        try:
            reference = provider.validate_reference(image_bytes)
        except face_recognition.FaceUnavailable as exc:
            # The engine is down/misconfigured — not a bad photo. Answer 503 so
            # the app can tell the user to retry rather than blame their face.
            return Response({"error": str(exc)}, status=503)
        except face_recognition.FaceError as exc:
            return Response({"error": str(exc)}, status=400)

        # Ensure display ID exists
        if not staff.emp_id:
            staff._ensure_emp_id()
            staff.save(update_fields=["emp_id"])

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        qr_filename = generate_qr(emp_id, name, timestamp)

        # Only written once the photo has been accepted, so a rejected
        # registration leaves no orphan file behind.
        emp_image_folder = os.path.join(settings.MEDIA_ROOT, "emp_image")
        os.makedirs(emp_image_folder, exist_ok=True)

        image_filename = f"{emp_id}_{timestamp}.jpg"
        image_path = os.path.join(emp_image_folder, image_filename)
        with open(image_path, "wb") as f:
            f.write(image_bytes)

        relative_image_path = f"emp_image/{image_filename}"

        emp = Employee.objects.create(
            company_id=staff.company_id,
            project_id=staff.project_id,
            emp_id=staff.emp_id,
            staff=staff,
            name=name,
            department=department,
            image_path=relative_image_path,
            qr_code_path=qr_filename,
            dob=dob,
            blood_group=blood_group,
            face_embedding=reference.embedding,
        )

        return Response({
            "message": "Employee registered successfully",
            "emp_id": emp_id,
            "name": emp.name,
            "department": emp.department,
            "image": relative_image_path,
            "qr": qr_filename,
            "provider": provider.name,
        })
