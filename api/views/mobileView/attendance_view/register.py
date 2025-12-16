from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from datetime import datetime
from dateutil import parser
import os
from api.apps.attendance import Employee
from api.apps.utils.qr import generate_qr

class RegisterViewSet(ViewSet):

    def create(self, request):
        emp_id = request.data.get("emp_id")
        name = request.data.get("name")
        dob_str = request.data.get("dob")
        department = request.data.get("department")
        blood_group = request.data.get("blood_group")
        source_image = request.FILES.get("source_image")

        if not all([emp_id, name, department, source_image]):
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            dob = parser.parse(dob_str).date() if dob_str else None
        except:
            return Response({"error": "Invalid DOB"}, status=status.HTTP_400_BAD_REQUEST)

        # existing?
        if Employee.objects.filter(emp_id=emp_id).exists():
            emp = Employee.objects.get(emp_id=emp_id)
            return Response({
                "message": "Employee already registered",
                "emp_id": emp.emp_id,
                "name": emp.name,
                "department": emp.department,
                "image": emp.image_path,
                "qr": emp.qr_code_path
            })

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # # save image
        # upload_folder = os.path.join(settings.MEDIA_ROOT, "emp_image")
        # os.makedirs(upload_folder, exist_ok=True)

        # image_filename = f"{name}{emp_id}{timestamp}.jpg"
        # image_path = os.path.join(upload_folder, image_filename)

        # with open(image_path, "wb+") as f:
        #     for chunk in source_image.chunks():
        #         f.write(chunk)

        # qr_filename = generate_qr(emp_id, name, timestamp)

        # emp = Employee.objects.create(
        #     emp_id=emp_id,
        #     name=name,
        #     department=department,
        #     image_path=image_path,
        #     qr_code_path=qr_filename,
        #     dob=dob,
        #     blood_group=blood_group
        # )

        # return Response({
        #     "message": "Employee registered successfully",
        #     "emp_id": emp.emp_id,
        #     "name": emp.name,
        #     "department": emp.department,
        #     "image": image_filename,
        #     "qr": qr_filename
        # })
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from datetime import datetime
from dateutil import parser
import os

from api.apps.attendance import Employee
from api.apps.utils.qr import generate_qr


class RegisterViewSet(ViewSet):

    def create(self, request):
        emp_id = request.data.get("emp_id")
        name = request.data.get("name")
        dob_str = request.data.get("dob")
        department = request.data.get("department")
        blood_group = request.data.get("blood_group")
        source_image = request.FILES.get("source_image")

        if not all([emp_id, name, department, source_image]):
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            dob = parser.parse(dob_str).date() if dob_str else None
        except:
            return Response({"error": "Invalid DOB format"}, status=status.HTTP_400_BAD_REQUEST)

        # If employee already exists → return existing data
        if Employee.objects.filter(emp_id=emp_id).exists():
            emp = Employee.objects.get(emp_id=emp_id)
            return Response({
                "message": "Employee already registered",
                "emp_id": emp.emp_id,
                "name": emp.name,
                "department": emp.department,
                "image": emp.image_path,
                "qr": emp.qr_code_path
            })

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # MEDIA PATH (PHYSICAL LOCATION)
        upload_dir = os.path.join(settings.MEDIA_ROOT, "emp_image")
        os.makedirs(upload_dir, exist_ok=True)

        image_filename = f"{name}{emp_id}{timestamp}.jpg"
        physical_path = os.path.join(upload_dir, image_filename)

        # SAVE IMAGE PHYSICALLY
        with open(physical_path, "wb+") as f:
            for chunk in source_image.chunks():
                f.write(chunk)

        # RELATIVE PATH (stored in DB)
        relative_path = f"emp_image/{image_filename}"

        qr_filename = generate_qr(emp_id, name, timestamp)

        emp = Employee.objects.create(
            emp_id=emp_id,
            name=name,
            department=department,
            image_path=relative_path,  # <<– FIXED
            qr_code_path=qr_filename,
            dob=dob,
            blood_group=blood_group
        )

        return Response({
            "message": "Employee registered successfully",
            "emp_id": emp.emp_id,
            "name": emp.name,
            "department": emp.department,
            "image": relative_path,
            "qr": qr_filename
        })