from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from api.apps.attendance import Recognized
from django.conf import settings
import os


class AttendanceListViewSet(ViewSet):

    def _to_media_url(self, path):
        if not path:
            return None

        path = str(path).replace("\\", "/")

        if path.startswith("http"):
            return path

        media_root = settings.MEDIA_ROOT.replace("\\", "/")
        if media_root in path:
            path = path.split(media_root)[-1]

        return f"{settings.MEDIA_URL}{path.lstrip('/')}"

    def list(self, request):
        emp_id = request.query_params.get("emp_id")
        month = request.query_params.get("month")
        year = request.query_params.get("year")

        if not emp_id or not month or not year:
            return Response(
                {"status": "error", "message": "emp_id, month, year required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        records = Recognized.objects.filter(
            emp_id=emp_id,
            recognition_date__month=int(month),
            recognition_date__year=int(year),
        ).order_by("recognition_date", "recognition_time")

        dates = records.values_list(
            "recognition_date", flat=True
        ).distinct().order_by("-recognition_date")

        result = []

        for d in dates:
            day_records = records.filter(recognition_date=d)

            check_in = day_records.first()
            check_out = day_records.last()

            result.append({
                "date": d.strftime("%d/%B/%Y"),

                "in_time": check_in.recognition_time.strftime("%H:%M") if check_in else None,
                "out_time": (
                    check_out.recognition_time.strftime("%H:%M")
                    if check_out and check_out.id != check_in.id
                    else None
                ),

                "in_latitude": check_in.latitude if check_in else None,
                "in_longitude": check_in.longitude if check_in else None,
                "out_latitude": check_out.latitude if check_out else None,
                "out_longitude": check_out.longitude if check_out else None,

                "in_image_path": self._to_media_url(
                    check_in.captured_image_path if check_in else None
                ),
                "out_image_path": self._to_media_url(
                    check_out.captured_image_path
                    if check_out and check_out.id != check_in.id
                    else None
                ),
            })

        return Response(
            {
                "status": "success",
                "count": len(result),
                "records": result
            },
            status=status.HTTP_200_OK
        )
