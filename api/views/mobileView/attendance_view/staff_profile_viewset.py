# from rest_framework.viewsets import ViewSet
# from rest_framework.response import Response
# from rest_framework import status
# from api.apps.attendance import Employee
# from api.apps.userCreation import User
# from api.apps.staffcreation import StaffOfficeDetails, StaffPersonalDetails


# class StaffProfileViewSet(ViewSet):
#     """
#     Input: staff_id_id (User.staff_id → FK to StaffOfficeDetails)
#     Output: Full staff profile joined from 3 tables:
#         - api_user
#         - api_officedetails
#         - api_personaldetails
#     """

#     def list(self, request):
#         staff_id = request.query_params.get("staff_id_id")

#         if not staff_id:
#             return Response(
#                 {"error": "staff_id_id is required"},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         # 1) Match in api_user
#         user = User.objects.filter(staff_id_id=staff_id).first()

#         if not user:
#             return Response(
#                 {"error": "Staff not found in api_user"},
#                 status=status.HTTP_404_NOT_FOUND
#             )

#         # 2) Fetch Office Details
#         office = StaffOfficeDetails.objects.filter(id=staff_id).first()

#         if not office:
#             return Response(
#                 {"error": "Office details not found"},
#                 status=status.HTTP_404_NOT_FOUND
#             )

#         # 3) Fetch Personal Details
#         personal = StaffPersonalDetails.objects.filter(staff_id=staff_id).first()

#         # Build response
#         data = {
#             "staff_id": staff_id,
#             "employee_name": office.employee_name,
#             "department": office.department,
#             "designation": office.designation,
#             "site_name": office.site_name,
#             "doj": office.doj,
            
#             # Personal section
#             "dob": personal.dob if personal else None,
#             "blood_group": personal.blood_group if personal else None,
#         }

#         return Response({"status": True, "data": data}, status=status.HTTP_200_OK)
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
import os

from api.apps.staffcreation import StaffOfficeDetails, StaffPersonalDetails
from api.serializers.mobileView.employee import (
    StaffOfficeSerializer,
    StaffUpdateSerializer,
)


# class StaffProfileViewSet(viewsets.ViewSet):
#     parser_classes = (MultiPartParser, FormParser)

#     # -----------------------------------
#     # GET Profile (staff_id_id = User.staff_id_id)
#     # -----------------------------------
#     def list(self, request):
#         staff_id = request.query_params.get("staff_id_id")

#         if not staff_id:
#             return Response(
#                 {"status": "error", "message": "staff_id_id is required"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             staff = StaffOfficeDetails.objects.get(id=staff_id)
#         except StaffOfficeDetails.DoesNotExist:
#             return Response(
#                 {"status": "error", "message": "Staff profile not found"},
#                 status=status.HTTP_404_NOT_FOUND,
#             )

#         serializer = StaffOfficeSerializer(staff)
#         return Response({"status": "success", "data": serializer.data})

#     # -----------------------------------
#     # UPDATE Profile
#     # -----------------------------------
#     def update(self, request, pk=None):
#         try:
#             staff = StaffOfficeDetails.objects.get(id=pk)
#         except StaffOfficeDetails.DoesNotExist:
#             return Response(
#                 {"status": "error", "message": "Staff not found"},
#                 status=status.HTTP_404_NOT_FOUND,
#             )

#         serializer = StaffUpdateSerializer(staff, data=request.data, partial=True)

#         if serializer.is_valid():
#             serializer.save()

#             # UPDATE personal details
#             dob = request.data.get("dob")
#             blood_group = request.data.get("blood_group")

#             personal, created = StaffPersonalDetails.objects.get_or_create(
#                 staff=staff
#             )
#             if dob:
#                 personal.dob = dob
#             if blood_group:
#                 personal.blood_group = blood_group
#             personal.save()

#             return Response(
#                 {"status": "success", "message": "Profile updated successfully"},
#                 status=status.HTTP_200_OK,
#             )

#         return Response(
#             {"status": "error", "message": serializer.errors},
#             status=status.HTTP_400_BAD_REQUEST,
#         )
class StaffProfileViewSet(viewsets.ViewSet):
    parser_classes = (MultiPartParser, FormParser)

    def list(self, request):
        staff_id = request.query_params.get("staff_id_id")

        if not staff_id:
            return Response(
                {"status": "error", "message": "staff_id_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ------------------------------------------
        # 1️⃣ Get StaffOfficeDetails
        # ------------------------------------------
        try:
            staff = StaffOfficeDetails.objects.get(id=staff_id)
        except StaffOfficeDetails.DoesNotExist:
            return Response(
                {"status": "error", "message": "Staff profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Serialize office/staff details
        data = StaffOfficeSerializer(staff).data

        # ------------------------------------------
        # 2️⃣ Fetch EMPLOYEE SELFIE from Employee table
        # ------------------------------------------
        try:
            from api.models import Employee  # adjust import

            employee = Employee.objects.get(emp_id=staff.id)
            image_path = employee.image_path     # full path like ".../emp_image/name123.jpg"

            # only return filename, not full path
            filename = os.path.basename(image_path)

            data["photo"] = f"emp_image/{filename}"

        except Employee.DoesNotExist:
            data["photo"] = None

        return Response({"status": "success", "data": data})

    # ------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------
    def update(self, request, pk=None):
        try:
            staff = StaffOfficeDetails.objects.get(id=pk)
        except StaffOfficeDetails.DoesNotExist:
            return Response(
                {"status": "error", "message": "Staff not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = StaffUpdateSerializer(staff, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()

            # update personal details
            dob = request.data.get("dob")
            blood_group = request.data.get("blood_group")

            personal, created = StaffPersonalDetails.objects.get_or_create(
                staff=staff
            )
            if dob:
                personal.dob = dob
            if blood_group:
                personal.blood_group = blood_group
            personal.save()

            return Response(
                {"status": "success", "message": "Profile updated successfully"},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"status": "error", "message": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
