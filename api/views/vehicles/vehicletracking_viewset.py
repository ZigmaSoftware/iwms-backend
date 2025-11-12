from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


from ...apps.vehiclehistory import fetch_vehicle_history, VehicleHistoryError



class VehicleHistoryView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            data = fetch_vehicle_history(request.data)
            return Response(data, status=status.HTTP_200_OK)
        except VehicleHistoryError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)
