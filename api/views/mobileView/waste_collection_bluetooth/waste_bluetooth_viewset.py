from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.response import Response
from django.utils import timezone
from django.db import connection
from ....apps.waste_collection_bluetooth import generate_unique_id, upload_image


class WasteCollectionViewSet(viewsets.ViewSet):
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    # ----------------- INSERT WASTE SUB -----------------
    @action(detail=False, methods=["post"], url_path="insert-waste-sub")
    def insert_waste_sub(self, request):
        screen_id = request.data.get("screen_unique_id")
        customer_id = request.data.get("customer_id")
        waste_type = request.data.get("waste_type")
        weight = request.data.get("weight")
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")
        image = request.FILES.get("image")

        if not screen_id:
            return Response({"status": "error", "message": "Missing screen_unique_id"}, status=400)
        if not image:
            return Response({"status": "error", "message": "No image uploaded"}, status=400)

        unique_id = generate_unique_id("wcs")
        image_path = upload_image(image)
        now = timezone.now()

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO waste_collection_sub
                (unique_id, screen_unique_id, customer_id, waste_type_id, image, weight,
                 latitude, longitude, date_time, is_delete)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0)
            """, [unique_id, screen_id, customer_id, waste_type, image_path,
                  weight, latitude, longitude, now])

        return Response({
            "status": "success",
            "unique_id": unique_id,
            "screen_unique_id": screen_id,
            "image": image_path
        })

    # ----------------- GET SAVED WASTE TYPES -----------------
    @action(detail=False, methods=["get"], url_path="get-waste-types")
    def get_saved_waste(self, request):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, waste_type_name
                FROM waste_type_creation_master
                WHERE is_delete=0
                ORDER BY id ASC
            """)
            rows = cursor.fetchall()
        data = [{"id": r[0], "waste_type_name": r[1]} for r in rows]
        return Response({"status": "success", "count": len(data), "data": data})

    # ----------------- GET LATEST WASTE SUB -----------------
    @action(detail=False, methods=["post"], url_path="get-latest-waste")
    def get_latest_waste(self, request):
        screen_id = request.data.get("screen_unique_id")
        customer_id = request.data.get("customer_id")
        waste_type = request.data.get("waste_type")

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, unique_id, waste_type_id, image, weight
                FROM waste_collection_sub
                WHERE screen_unique_id=%s
                AND customer_id=%s
                AND waste_type_id=%s
                AND is_delete=0
                ORDER BY id DESC LIMIT 1
            """, [screen_id, customer_id, waste_type])
            row = cursor.fetchone()

        if not row:
            return Response({"status": "error", "message": "No record found"})

        return Response({
            "status": "success",
            "data": {
                "id": row[0],
                "unique_id": row[1],
                "waste_type_id": row[2],
                "image": row[3],
                "weight": row[4],
            }
        })

    # ----------------- FINALIZE WASTE COLLECTION -----------------
    @action(detail=False, methods=["post"], url_path="finalize-waste")
    def finalize_waste_collection(self, request):
        screen_id = request.data.get("screen_unique_id")
        customer_id = request.data.get("customer_id")
        entry_type = request.data.get("entry_type", "app")

        if not screen_id or not customer_id:
            return Response({"status": "error", "message": "Missing parameters"}, status=400)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM(weight), 0)
                FROM waste_collection_sub
                WHERE screen_unique_id=%s AND customer_id=%s AND is_delete=0
            """, [screen_id, customer_id])
            total = cursor.fetchone()[0]

        if float(total) <= 0:
            return Response({"status": "error", "message": "No waste records found"})

        main_id = generate_unique_id("wcm")
        now = timezone.now()

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO waste_collection_main
                (unique_id, screen_unique_id, collected_time, created,
                 total_waste_collected, entry_type, customer_id, is_delete)
                VALUES (%s,%s,%s,%s,%s,%s,%s,0)
            """, [main_id, screen_id, now, now, total, entry_type, customer_id])

        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE waste_collection_sub
                SET form_unique_id=%s
                WHERE screen_unique_id=%s AND customer_id=%s AND is_delete=0
            """, [main_id, screen_id, customer_id])

        return Response({
            "status": "success",
            "main_unique_id": main_id,
            "total_weight": float(total),
            "collected_time": now
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

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT unique_id
                FROM waste_collection_sub
                WHERE unique_id=%s AND is_delete=0
            """, [record_id])
            row = cursor.fetchone()

        if row is None:
            return Response({"status": "error", "message": f"No matching record found for unique_id {record_id}"}, status=400)

        image_path = None
        if "image" in request.FILES:
            image_path = upload_image(request.FILES["image"])

        now = timezone.now()

        sql = """
            UPDATE waste_collection_sub
            SET weight=%s, latitude=%s, longitude=%s, date_time=%s
        """
        params = [weight, latitude, longitude, now]

        if image_path:
            sql += ", image=%s"
            params.append(image_path)

        sql += " WHERE unique_id=%s AND is_delete=0"
        params.append(record_id)

        with connection.cursor() as cursor:
            cursor.execute(sql, params)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT unique_id, waste_type_id, image, weight, latitude, longitude
                FROM waste_collection_sub
                WHERE unique_id=%s
            """, [record_id])
            updated = cursor.fetchone()

        return Response({
            "status": "success",
            "message": "Record updated",
            "data": {
                "unique_id": updated[0],
                "waste_type_id": updated[1],
                "image": updated[2],
                "weight": updated[3],
                "latitude": updated[4],
                "longitude": updated[5],
            }
        })
