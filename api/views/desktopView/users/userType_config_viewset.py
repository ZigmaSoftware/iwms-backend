from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from api.apps.userType import UserType

class UserTypeConfigView(APIView):
    def get(self, request, pk):
        try:
            user_type = UserType.objects.get(pk=pk)
        except UserType.DoesNotExist:
            return Response({"error": "Invalid user type"}, status=status.HTTP_404_NOT_FOUND)

        name = user_type.name.lower().strip()

        # ===========================
        # CUSTOMER CONFIG
        # ===========================
        if name == "customer":
            config = {
                "user_type": "Customer",

                # Fields allowed to edit/enable at frontend
                "enabled_fields": ["customer_id", "district_id", "city_id", "zone_id", "ward_id"],

                # Fields completely disabled
                "disabled_fields": ["staffusertype_id", "staff_id"],

                # Mandatory fields
                "required_fields": ["customer_id"],   # 👈 IMPORTANT

                # API endpoint sources
                "data_sources": {
                    "customer_id": "/customercreations/",
                    "district_id": "/districts/",
                    "city_id": "/cities/",
                    "zone_id": "/zones/",
                    "ward_id": "/wards/"
                }
            }

        # ===========================
        # STAFF CONFIG
        # ===========================
        elif name == "staff":
            config = {
                "user_type": "Staff",

                "enabled_fields": ["staffusertype_id", "staff_id", "district_id", "city_id", "zone_id", "ward_id"],

                "disabled_fields": ["customer_id"],

                "required_fields": ["staffusertype_id", "staff_id"],  # 👈 STAFF MANDATORY

                "data_sources": {
                    "staffusertype_id": "/staffusertypes/",
                    "staff_id": "/staffcreation/",
                    "district_id": "/districts/",
                    "city_id": "/cities/",
                    "zone_id": "/zones/",
                    "ward_id": "/wards/"
                }
            }

        # ===========================
        # OTHER / UNKNOWN
        # ===========================
        else:
            config = {
                "user_type": user_type.name,
                "enabled_fields": [],
                "disabled_fields": [
                    "customer_id", "staffusertype_id", "staff_id",
                    "district_id", "city_id", "zone_id", "ward_id"
                ],
                "required_fields": [],
                "data_sources": {}
            }

        return Response(config, status=status.HTTP_200_OK)
