from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Case, IntegerField, Q, Sum, Value, When
from datetime import datetime, timedelta
from app.models.user_creations.waste_collection_bluetooth import (
    WasteCollectionMain,
    WasteCollectionSub,
    WasteType,
    upload_image,
)
from app.models.customers.customercreation import CustomerCreation
from app.models.customers.wastecollection import WasteCollection
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment



class WasteCollectionBluetoothViewSet(viewsets.ViewSet):
    parser_classes = [JSONParser, FormParser, MultiPartParser]
        # ----------------- API ROOT FOR /waste/ -----------------
    def list(self, request):
        """
        Waste API root endpoint.
        Shows all available waste-related operations.
        """
        base = request.build_absolute_uri().rstrip("/")

        return Response({
            "status": "success",
            "message": "Waste collection API root",
            "available_endpoints": {
                "get_waste_types": f"{base}/get-waste-types/",
                "insert_waste_sub": f"{base}/insert-waste-sub/",
                "get_latest_waste": f"{base}/get-latest-waste/",
                "update_waste_sub": f"{base}/update-waste-sub/",
                "finalize_waste": f"{base}/finalize-waste/",
                "citizen_summary": f"{base}/citizen-summary/",
                "mark_household_status": f"{base}/mark-household-status/",
            }
        })

    # ----------------- MARK HOUSEHOLD STATUS (Not available / Collect later) -----------------
    @action(detail=False, methods=["post"], url_path="mark-household-status")
    def mark_household_status(self, request):
        """Driver marks a household stop Not Available or Collect Later from
        the app — the counterpart to insert-waste-sub/finalize-waste for the
        two "can't collect right now" outcomes.

        This endpoint previously did not exist at all (the mobile app's
        `waste/mark-household-status/` call 404'd unconditionally); ported
        from the government backend's working implementation, adapted to
        this backend's available helpers (no audit-log/push-notification
        wiring here — neither exists in this backend yet, and no other
        endpoint in this file does either).

        Writes directly to the DailyTripHouseholdCollection row for the
        given trip assignment, via DailyTripHouseholdCollection.mark_status
        (see that model) — the same status field the trip API
        (operator-mobile/my-trip(s)-today/) reads, so the change is visible
        to the driver immediately on refresh.
        """
        from app.models.schedule_masters.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )
        from app.viewsets.operator_mobile.helpers import (
            OperatorFlowError,
            find_active_assignment_for_operator,
            require_trip_started,
            resolve_operator_staff,
        )

        customer_id = str(request.data.get("customer_id") or "").strip()
        status_value = str(request.data.get("status") or "").strip().lower()
        reason = str(
            request.data.get("reason") or request.data.get("status_reason") or ""
        ).strip()
        latitude = request.data.get("latitude") or None
        longitude = request.data.get("longitude") or None

        status_aliases = {
            # "Not available" from the app → canonical "Not Available".
            "not_available": DailyTripHouseholdCollection.STATUS_MISSED,
            "not available": DailyTripHouseholdCollection.STATUS_MISSED,
            "missed": DailyTripHouseholdCollection.STATUS_MISSED,
            # "Collect later" → canonical "Collect Later" (matches the web).
            "collect_later": DailyTripHouseholdCollection.STATUS_COLLECT_LATER,
            "collect later": DailyTripHouseholdCollection.STATUS_COLLECT_LATER,
            "skipped": DailyTripHouseholdCollection.STATUS_COLLECT_LATER,
        }
        normalized_status = status_aliases.get(status_value)

        if not customer_id:
            return Response(
                {"status": "error", "message": "customer_id is required"}, status=400
            )
        if normalized_status is None:
            return Response(
                {
                    "status": "error",
                    "message": "status must be missed/not_available or skipped/collect_later",
                },
                status=400,
            )
        if not reason:
            return Response(
                {"status": "error", "message": "reason is required"}, status=400
            )

        try:
            staff = resolve_operator_staff(request.user)
            # The app sends the specific trip the household belongs to (a
            # driver can have both a bin AND a household trip today). Use it
            # so the status lands on the correct household assignment;
            # otherwise fall back to the operator's active trip.
            assignment_id = str(request.data.get("assignment_id") or "").strip()
            assignment = None
            if assignment_id:
                assignment = DailyTripAssignment.objects.filter(
                    unique_id=assignment_id, is_deleted=False
                ).first()
            if assignment is None:
                assignment = find_active_assignment_for_operator(staff)
            require_trip_started(assignment)
        except OperatorFlowError as exc:
            return Response(
                {"status": "error", "code": exc.code, "message": exc.message},
                status=exc.http_status,
            )

        customer = CustomerCreation.objects.filter(
            Q(unique_id=customer_id) | Q(customer_id=customer_id),
            is_deleted=False,
        ).first()
        if customer is None:
            return Response(
                {"status": "error", "message": "Customer not found"}, status=404
            )

        # Allow marking ANY customer, even one not pre-listed on the trip:
        # attach them to the requester's active assignment as a household
        # stop on the fly.
        dthc = (
            DailyTripHouseholdCollection.objects
            .filter(
                trip_assignment_id=assignment,
                customer_id=customer,
                is_deleted=False,
            )
            .first()
        )
        if dthc is None:
            last_seq = (
                DailyTripHouseholdCollection.objects
                .filter(trip_assignment_id=assignment)
                .order_by("-sequence")
                .values_list("sequence", flat=True)
                .first()
            )
            dthc = DailyTripHouseholdCollection.objects.create(
                trip_assignment_id=assignment,
                customer_id=customer,
                collection_type=DailyTripHouseholdCollection.COLLECTION_TYPE_HOUSEHOLD,
                sequence=(last_seq or 0) + 1,
                status=DailyTripHouseholdCollection.STATUS_PENDING,
                is_collected=False,
                is_active=True,
                is_deleted=False,
            )
        if dthc.is_collected:
            return Response(
                {"status": "error", "message": "This household is already collected."},
                status=409,
            )

        dthc.mark_status(
            normalized_status, reason=reason, latitude=latitude, longitude=longitude,
        )
        # "Not Available" resolves the stop for the day same as a real
        # collection does (see pending_household_stops); "Collect Later"
        # doesn't, so this is a safe no-op when stops are still pending.
        assignment.mark_completed_if_all_household_stops_collected()

        return Response({
            "status": "success",
            "data": {
                "unique_id": dthc.unique_id,
                "customer_id": dthc.customer_id_id,
                "trip_assignment_id": dthc.trip_assignment_id_id,
                "collection_status": dthc.status,
                "reason": dthc.status_reason,
            },
        })

    # ----------------- INSERT WASTE SUB -----------------
    @action(detail=False, methods=["post"], url_path="insert-waste-sub")
    def insert_waste_sub(self, request):
        screen_id = request.data.get("screen_unique_id")
        customer_id = request.data.get("customer_id")
        waste_type = request.data.get("waste_type") or request.data.get(
            "waste_type_id"
        )
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

        # ORM insert (was raw SQL against the non-existent table
        # `waste_collection_sub` — the real Django-managed table is
        # `app_wastecollectionsub`, via the WasteCollectionSub model).
        # `unique_id` is left to the model's own default (generate_unique_id
        # is still imported for update_waste_sub's response payload usage
        # elsewhere, but insert no longer needs the raw "wcs" prefix version
        # since the model already generates "wcs-...").
        row = WasteCollectionSub.objects.create(
            screen_unique_id=screen_id,
            customer_id=customer_id,
            waste_type_id=waste_type,
            image=image_path,
            weight=weight or 0,
            latitude=latitude,
            longitude=longitude,
        )

        return Response({
            "status": "success",
            "unique_id": row.unique_id,
            "screen_unique_id": screen_id,
            "image": image_path
        })

    # ----------------- GET SAVED WASTE TYPES -----------------
    @action(detail=False, methods=["get"], url_path="get-waste-types")
    def get_saved_waste(self, request):
        customer_id = (request.query_params.get("customer_id") or "").strip()
        waste_types = WasteType.objects.filter(is_deleted=False)

        if customer_id:
            customer = (
                CustomerCreation.objects.filter(
                    Q(unique_id=customer_id) | Q(customer_id=customer_id),
                    is_deleted=False,
                )
                .prefetch_related("waste_types")
                .first()
            )
            waste_types = (
                customer.waste_types.filter(is_deleted=False)
                if customer
                else WasteType.objects.none()
            )

        waste_types = waste_types.annotate(
            sort_order=Case(
                When(waste_type_name__iexact="Wet Waste", then=Value(0)),
                When(waste_type_name__iexact="Dry Waste", then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            )
        ).order_by("sort_order", "waste_type_name")
        data = [
            {
                "id": wt.unique_id,
                "unique_id": wt.unique_id,
                "waste_type_name": wt.waste_type_name,
            }
            for wt in waste_types
        ]
        return Response({"status": "success", "count": len(data), "data": data})

    # ----------------- GET LATEST WASTE SUB -----------------
    @action(detail=False, methods=["post"], url_path="get-latest-waste")
    def get_latest_waste(self, request):
        screen_id = request.data.get("screen_unique_id")
        customer_id = request.data.get("customer_id")
        waste_type = request.data.get("waste_type") or request.data.get(
            "waste_type_id"
        )
        if not waste_type:
            return Response({"status": "error", "message": "Missing waste_type"}, status=400)

        # WasteCollectionSub has no auto-increment `id` (unique_id is the
        # primary key, generated with a timestamp component), so "latest"
        # means most recently written rather than highest id.
        row = (
            WasteCollectionSub.objects.filter(
                screen_unique_id=screen_id,
                customer_id=customer_id,
                waste_type_id=waste_type,
                is_deleted=False,
            )
            .order_by("-date_time")
            .first()
        )

        if not row:
            return Response({"status": "error", "message": "No record found"})

        return Response({
            "status": "success",
            "data": {
                "unique_id": row.unique_id,
                "waste_type_id": row.waste_type_id,
                "image": row.image,
                "weight": row.weight,
            }
        })

    # ----------------- FINALIZE WASTE COLLECTION -----------------
    @action(detail=False, methods=["post"], url_path="finalize-waste")
    def finalize_waste_collection(self, request):
        screen_id = request.data.get("screen_unique_id")
        customer_id = request.data.get("customer_id")
        entry_type = request.data.get("entry_type", "app")
        assignment_id = (request.data.get("assignment_id") or "").strip()

        if not screen_id or not customer_id:
            return Response({"status": "error", "message": "Missing parameters"}, status=400)

        sub_rows = WasteCollectionSub.objects.filter(
            screen_unique_id=screen_id, customer_id=customer_id, is_deleted=False,
        )
        total = sub_rows.aggregate(total=Sum("weight"))["total"] or 0

        if float(total) <= 0:
            return Response({"status": "error", "message": "No waste records found"})

        now = timezone.now()
        main = WasteCollectionMain.objects.create(
            screen_unique_id=screen_id,
            collected_time=now,
            created=now,
            total_waste_collected=total,
            entry_type=entry_type,
            customer_id=customer_id,
        )

        sub_rows.update(form_unique_id=main.unique_id)

        # Mirror this finalize into the real WasteCollection model, scoped to
        # the trip assignment the driver was actually working. Without this,
        # a finalize here only ever wrote to the legacy
        # WasteCollectionMain/Sub tables — which nothing else in the system
        # reads — so a household stop's card in the app never showed as
        # collected, no weight ever reached DailyTripHouseholdCollection or
        # the trip's DailyTripLog, and panchayat-level waste reports (which
        # read WasteCollection) silently missed every collection made this
        # way. Creating a WasteCollection row here fires
        # sync_household_collection_on_waste_save (see
        # app/signals/trip_plan_signals.py), which does all of that —
        # marking the stop Collected with this weight, and rolling it into
        # the trip log — the same as the properly-wired
        # schedule-operations/wastecollections/ API path.
        household_note = self._sync_to_household_collection(
            customer_id=customer_id,
            assignment_id=assignment_id,
            sub_rows=sub_rows,
            total=total,
        )

        return Response({
            "status": "success",
            "main_unique_id": main.unique_id,
            "total_weight": float(total),
            "collected_time": now,
            "household_sync": household_note,
        })

    def _sync_to_household_collection(self, *, customer_id, assignment_id, sub_rows, total):
        """Best-effort bridge from the legacy sub/main tables into the real
        WasteCollection model — see the call site's comment for why this
        exists. Returns a short status string for the response payload
        (never raises: a driver's collection must not be lost over a
        secondary-sync failure once the legacy rows above are already
        committed).
        """
        if not assignment_id:
            return "skipped: no assignment_id"

        try:
            customer = CustomerCreation.objects.filter(
                Q(unique_id=customer_id) | Q(customer_id=customer_id),
                is_deleted=False,
            ).first()
            if customer is None:
                return "skipped: customer not found"

            assignment = DailyTripAssignment.objects.filter(
                unique_id=assignment_id, is_deleted=False,
            ).first()
            if assignment is None:
                return "skipped: assignment not found"

            # Split the summed weight across WasteCollection's fixed
            # wet/dry/mixed/sanitary columns by each sub-row's waste-type
            # name — the legacy schema has no such split, only a flat
            # `waste_type_id` per row.
            waste_type_ids = set(
                sub_rows.values_list("waste_type_id", flat=True).distinct()
            )
            names_by_id = dict(
                WasteType.objects.filter(unique_id__in=waste_type_ids).values_list(
                    "unique_id", "waste_type_name"
                )
            )
            buckets = {"wet_waste": 0.0, "dry_waste": 0.0, "mixed_waste": 0.0, "sanitary_waste": 0.0}
            for waste_type_id, weight in sub_rows.values_list("waste_type_id", "weight"):
                name = (names_by_id.get(waste_type_id) or "").strip().lower()
                if "wet" in name:
                    buckets["wet_waste"] += float(weight or 0)
                elif "dry" in name:
                    buckets["dry_waste"] += float(weight or 0)
                elif "sanitary" in name:
                    buckets["sanitary_waste"] += float(weight or 0)
                else:
                    buckets["mixed_waste"] += float(weight or 0)

            WasteCollection.objects.create(
                customer=customer,
                trip_assignment_id=assignment,
                # Inherited from the assignment, not left blank: WasteCollection
                # is a CompanyScopedViewSet model, and any company-scoped list
                # (e.g. the supervisor app's `wastecollections/?mine=true`)
                # filters by company_id/project_id — a null value here silently
                # excludes the row from every such list, even though nothing
                # about the create itself fails.
                company_id=assignment.company_id,
                project_id=assignment.project_id,
                collection_date=timezone.localdate(),
                **buckets,
                # total_quantity is recomputed in WasteCollection.save() from
                # the buckets above; the post_save signal marks the matching
                # DailyTripHouseholdCollection stop Collected and syncs the
                # trip's DailyTripLog automatically.
            )
            return "synced"
        except Exception as exc:  # noqa: BLE001 — best-effort, see docstring
            return f"failed: {exc}"

    # ----------------- UPDATE WASTE SUB -----------------
    @action(detail=False, methods=["post"], url_path="update-waste-sub")
    def update_waste_sub(self, request):
        record_id = request.data.get("unique_id") or request.data.get("id")
        weight = request.data.get("weight")
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")

        if not record_id:
            return Response({"status": "error", "message": "Missing unique_id"}, status=400)

        row = WasteCollectionSub.objects.filter(
            unique_id=record_id, is_deleted=False,
        ).first()
        if row is None:
            return Response({"status": "error", "message": f"No matching record found for unique_id {record_id}"}, status=400)

        image_path = None
        if "image" in request.FILES:
            image_path = upload_image(request.FILES["image"])

        row.weight = weight or 0
        row.latitude = latitude
        row.longitude = longitude
        row.date_time = timezone.now()
        update_fields = ["weight", "latitude", "longitude", "date_time"]
        if image_path:
            row.image = image_path
            update_fields.append("image")
        row.save(update_fields=update_fields)

        return Response({
            "status": "success",
            "message": "Record updated",
            "data": {
                "unique_id": row.unique_id,
                "waste_type_id": row.waste_type_id,
                "image": row.image,
                "weight": row.weight,
                "latitude": row.latitude,
                "longitude": row.longitude,
            }
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
                {
                    "status": "error",
                    "message": "Invalid date format. Use YYYY-MM-DD.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        start, end = self._get_range_bounds(period, base_date)
        start = self._make_aware(start)
        end = self._make_aware(end)

        weights = {"wet": 0.0, "dry": 0.0, "mixed": 0.0}
        params = []
        date_filter = ""

        if start and end:
            date_filter = " AND date_time >= %s AND date_time < %s"
            params.extend([start, end])

        sub_qs = WasteCollectionSub.objects.filter(is_deleted=False)
        if start and end:
            sub_qs = sub_qs.filter(date_time__gte=start, date_time__lt=end)
        rows = (
            sub_qs.values("waste_type_id")
            .annotate(total=Sum("weight"))
            .values_list("waste_type_id", "total")
        )

        for waste_type_id, total in rows:
            key = str(waste_type_id)
            total_value = float(total or 0)
            if key == "1":
                weights["wet"] = total_value
            elif key == "2":
                weights["dry"] = total_value
            else:
                weights["mixed"] += total_value

        main_qs = WasteCollectionMain.objects.filter(is_deleted=False)
        if start and end:
            main_qs = main_qs.filter(collected_time__gte=start, collected_time__lt=end)
        total_trip = main_qs.count()
        total_net = weights["wet"] + weights["dry"] + weights["mixed"]
        average_per_trip = total_net / total_trip if total_trip > 0 else 0.0

        summary_date = start.date() if start else timezone.localdate()

        return Response(
            {
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
            }
        )

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

    # ----------------- LOOKUP CUSTOMER BY UNIQUE ID FOR QR -----------------
    @action(detail=False, methods=["get"], url_path="customer")
    def get_customer_by_unique_id(self, request):
        unique_id = request.query_params.get("unique_id") or request.query_params.get("uid")
        if not unique_id:
            return Response(
                {"status": "error", "message": "unique_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Match directly on customer unique_id
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

        data = {
            "unique_id": customer.unique_id,
            "customer_name": customer.customer_name,
            "contact_no": customer.contact_no,
            "latitude": customer.latitude,
            "longitude": customer.longitude,
            "address": {
                "building_no": customer.building_no,
                "street": customer.street,
                "area": customer.area,
                "pincode": customer.pincode,
            },
        }

        return Response({"status": "success", "data": data})
