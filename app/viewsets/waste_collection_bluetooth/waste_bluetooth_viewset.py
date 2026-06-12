from datetime import datetime, timedelta

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.response import Response
from django.db.models import Sum
from django.utils import timezone

from app.models.user_creations.waste_collection_bluetooth import (
    WasteType,
    WasteCollectionSub,
    WasteCollectionMain,
    generate_unique_id,
    upload_image,
)
from app.models.customers.customercreation import CustomerCreation


class WasteCollectionBluetoothViewSet(viewsets.ViewSet):
    """Operator *household* waste-entry API, mounted at ``/api/v1/waste/``.

    Serves the operator mobile "Household collection" flow (OperatorQRScanner →
    OperatorDataScreen): scan a customer QR, then record wet/dry/mixed waste
    with per-type weights (Bluetooth scale or manual) + photos, and finalize.

    Implemented on the current ORM models (WasteType / WasteCollectionSub /
    WasteCollectionMain) so it tracks the live schema automatically. It is fully
    independent of the ORM CRUD endpoints under ``/waste-bluetooth/`` — both can
    coexist without disturbing each other.
    """

    parser_classes = [JSONParser, FormParser, MultiPartParser]

    # ----------------- API ROOT FOR /waste/ -----------------
    def list(self, request):
        base = request.build_absolute_uri().rstrip("/")
        return Response({
            "status": "success",
            "message": "Waste collection API root",
            "available_endpoints": {
                "get_waste_types": f"{base}/get-waste-types/",
                "customer": f"{base}/customer/?unique_id=CUS-...",
                "insert_waste_sub": f"{base}/insert-waste-sub/",
                "get_latest_waste": f"{base}/get-latest-waste/",
                "update_waste_sub": f"{base}/update-waste-sub/",
                "finalize_waste": f"{base}/finalize-waste/",
                "citizen_summary": f"{base}/citizen-summary/",
            },
        })

    # ----------------- GET SAVED WASTE TYPES -----------------
    @action(detail=False, methods=["get"], url_path="get-waste-types")
    def get_saved_waste(self, request):
        # The mobile app keys everything off a numeric/string "id"; the model's
        # PK is `unique_id`, so expose that as `id` to keep the contract stable.
        rows = (
            WasteType.objects
            .filter(is_deleted=False)
            .order_by("unique_id")
            .values_list("unique_id", "waste_type_name")
        )
        data = [{"id": uid, "waste_type_name": name} for uid, name in rows]
        return Response({"status": "success", "count": len(data), "data": data})

    # ----------------- INSERT WASTE SUB -----------------
    @action(detail=False, methods=["post"], url_path="insert-waste-sub")
    def insert_waste_sub(self, request):
        screen_id = request.data.get("screen_unique_id")
        customer_id = request.data.get("customer_id")
        waste_type = request.data.get("waste_type") or request.data.get("waste_type_id")
        weight = request.data.get("weight")
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")
        image = request.FILES.get("image")

        if not screen_id:
            return Response({"status": "error", "message": "Missing screen_unique_id"}, status=400)
        if not waste_type:
            return Response({"status": "error", "message": "Missing waste_type"}, status=400)
        if not image:
            return Response({"status": "error", "message": "No image uploaded"}, status=400)

        image_path = upload_image(image)
        record = WasteCollectionSub.objects.create(
            unique_id=generate_unique_id("wcs-"),
            screen_unique_id=screen_id,
            customer_id=customer_id,
            waste_type_id=str(waste_type),
            image=image_path,
            weight=self._to_float(weight),
            latitude=latitude,
            longitude=longitude,
            is_deleted=False,
        )

        return Response({
            "status": "success",
            "unique_id": record.unique_id,
            "screen_unique_id": screen_id,
            "image": image_path,
        })

    # ----------------- GET LATEST WASTE SUB -----------------
    @action(detail=False, methods=["post"], url_path="get-latest-waste")
    def get_latest_waste(self, request):
        screen_id = request.data.get("screen_unique_id")
        customer_id = request.data.get("customer_id")
        waste_type = request.data.get("waste_type") or request.data.get("waste_type_id")
        if not waste_type:
            return Response({"status": "error", "message": "Missing waste_type"}, status=400)

        record = (
            WasteCollectionSub.objects
            .filter(
                screen_unique_id=screen_id,
                customer_id=customer_id,
                waste_type_id=str(waste_type),
                is_deleted=False,
            )
            .order_by("-date_time")
            .first()
        )

        if not record:
            return Response({"status": "error", "message": "No record found"})

        return Response({
            "status": "success",
            "data": {
                "id": record.unique_id,
                "unique_id": record.unique_id,
                "waste_type_id": record.waste_type_id,
                "image": record.image,
                "weight": record.weight,
            },
        })

    # ----------------- UPDATE WASTE SUB -----------------
    @action(detail=False, methods=["post"], url_path="update-waste-sub")
    def update_waste_sub(self, request):
        record_id = request.data.get("unique_id") or request.data.get("id")
        weight = request.data.get("weight")
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")

        if not record_id:
            return Response({"status": "error", "message": "Missing unique_id"}, status=400)

        record = (
            WasteCollectionSub.objects
            .filter(unique_id=record_id, is_deleted=False)
            .first()
        )
        if record is None:
            return Response(
                {"status": "error", "message": f"No matching record found for unique_id {record_id}"},
                status=400,
            )

        record.weight = self._to_float(weight)
        record.latitude = latitude
        record.longitude = longitude
        if "image" in request.FILES:
            record.image = upload_image(request.FILES["image"])
        record.save()

        return Response({
            "status": "success",
            "message": "Record updated",
            "data": {
                "unique_id": record.unique_id,
                "waste_type_id": record.waste_type_id,
                "image": record.image,
                "weight": record.weight,
                "latitude": record.latitude,
                "longitude": record.longitude,
            },
        })

    # ----------------- FINALIZE WASTE COLLECTION -----------------
    @action(detail=False, methods=["post"], url_path="finalize-waste")
    def finalize_waste_collection(self, request):
        screen_id = request.data.get("screen_unique_id")
        customer_id = request.data.get("customer_id")
        entry_type = request.data.get("entry_type", "app")

        if not screen_id or not customer_id:
            return Response({"status": "error", "message": "Missing parameters"}, status=400)

        subs = WasteCollectionSub.objects.filter(
            screen_unique_id=screen_id,
            customer_id=customer_id,
            is_deleted=False,
        )
        total = subs.aggregate(total=Sum("weight"))["total"] or 0

        if float(total) <= 0:
            return Response({"status": "error", "message": "No waste records found"})

        now = timezone.now()
        main = WasteCollectionMain.objects.create(
            unique_id=generate_unique_id("wcm-"),
            screen_unique_id=screen_id,
            collected_time=now,
            created=now,
            total_waste_collected=float(total),
            entry_type=entry_type,
            customer_id=customer_id,
            is_deleted=False,
        )

        # Stamp the sub-rows with the finalized form id (audit trail).
        subs.update(form_unique_id=main.unique_id)

        return Response({
            "status": "success",
            "main_unique_id": main.unique_id,
            "total_weight": float(total),
            "collected_time": now,
        })

    # ----------------- LOOKUP CUSTOMER BY UNIQUE ID FOR QR -----------------
    @action(detail=False, methods=["get"], url_path="customer")
    def get_customer_by_unique_id(self, request):
        unique_id = request.query_params.get("unique_id") or request.query_params.get("uid")
        if not unique_id:
            return Response(
                {"status": "error", "message": "unique_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer = (
            CustomerCreation.objects
            .filter(unique_id=unique_id, is_deleted=False, is_active=True)
            .first()
        )
        if not customer:
            return Response(
                {"status": "error", "message": "Customer not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            "status": "success",
            "data": {
                "unique_id": customer.unique_id,
                "customer_id": customer.unique_id,
                "customer_name": customer.customer_name,
                "contact_no": customer.contact_no,
                "latitude": customer.latitude,
                "longitude": customer.longitude,
            },
        })

    # ----------------- CITIZEN WASTE SUMMARY (DAILY / MONTHLY / TOTAL) -----------------
    @action(detail=False, methods=["get"], url_path="citizen-summary")
    def citizen_summary(self, request):
        period = (request.query_params.get("period") or "monthly").lower()
        date_param = request.query_params.get("date")

        try:
            base_date = (
                datetime.strptime(date_param, "%Y-%m-%d").date()
                if date_param
                else timezone.localdate()
            )
        except ValueError:
            return Response(
                {"status": "error", "message": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        start, end = self._get_range_bounds(period, base_date)
        start = self._make_aware(start)
        end = self._make_aware(end)

        sub_qs = WasteCollectionSub.objects.filter(is_deleted=False)
        main_qs = WasteCollectionMain.objects.filter(is_deleted=False)
        if start and end:
            sub_qs = sub_qs.filter(date_time__gte=start, date_time__lt=end)
            main_qs = main_qs.filter(collected_time__gte=start, collected_time__lt=end)

        weights = {"wet": 0.0, "dry": 0.0, "mixed": 0.0}
        grouped = sub_qs.values("waste_type_id").annotate(total=Sum("weight"))
        for row in grouped:
            key = str(row["waste_type_id"]).lower()
            total_value = float(row["total"] or 0)
            if "1" == key or "wet" in key:
                weights["wet"] += total_value
            elif "2" == key or "dry" in key:
                weights["dry"] += total_value
            else:
                weights["mixed"] += total_value

        total_trip = main_qs.count()
        total_net = weights["wet"] + weights["dry"] + weights["mixed"]
        average_per_trip = total_net / total_trip if total_trip > 0 else 0.0
        summary_date = start.date() if start else timezone.localdate()

        return Response({
            "status": "success",
            "data": {
                "period": period,
                "date": summary_date.isoformat(),
                "total_trip": total_trip,
                "dry_weight": weights["dry"],
                "wet_weight": weights["wet"],
                "mix_weight": weights["mixed"],
                "total_net_weight": total_net,
                "average_weight_per_trip": average_per_trip,
            },
        })

    # ----------------- HELPERS -----------------
    @staticmethod
    def _to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _get_range_bounds(self, period, base_date):
        if period == "daily":
            start = datetime.combine(base_date, datetime.min.time())
            end = start + timedelta(days=1)
        elif period == "monthly":
            start = datetime(base_date.year, base_date.month, 1)
            if base_date.month == 12:
                end = datetime(base_date.year + 1, 1, 1)
            else:
                end = datetime(base_date.year, base_date.month + 1, 1)
        else:  # total or fallback
            start = None
            end = None
        return start, end

    def _make_aware(self, dt):
        if dt is None:
            return None
        if timezone.is_naive(dt):
            return timezone.make_aware(dt)
        return dt
