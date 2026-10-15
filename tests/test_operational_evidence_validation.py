from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIRequestFactory

from app.serializers.core_modules.daily_operations.daily_trip_log_serializer import (
    DailyTripLogSerializer,
)
from app.serializers.operator_mobile.scan_serializers import ScanBinRequestSerializer


def evidence_image():
    data = BytesIO()
    Image.new("RGB", (2, 2), color="white").save(data, format="PNG")
    return SimpleUploadedFile("proof.png", data.getvalue(), content_type="image/png")


def test_bin_not_available_requires_image_and_capture_coordinates():
    serializer = ScanBinRequestSerializer(
        data={
            "bin_qr": "BIN-1",
            "action": "not_available",
            "status_reason": "Access locked",
        }
    )

    assert not serializer.is_valid()
    assert set(serializer.errors) >= {"evidence_image", "latitude", "longitude"}


def test_bin_not_available_accepts_geotagged_evidence():
    serializer = ScanBinRequestSerializer(
        data={
            "bin_qr": "BIN-1",
            "action": "not_available",
            "status_reason": "Access locked",
            "latitude": "28.613900",
            "longitude": "77.209000",
            "evidence_image": evidence_image(),
        }
    )

    assert serializer.is_valid(), serializer.errors


def test_bin_collect_later_does_not_require_evidence():
    serializer = ScanBinRequestSerializer(
        data={
            "bin_qr": "BIN-1",
            "action": "collect_later",
            "status_reason": "Asked to return later",
        }
    )

    assert serializer.is_valid(), serializer.errors


def test_trip_log_household_status_evidence_uses_absolute_url():
    request = APIRequestFactory().get("/api/v1/daily-trip-logs/TRIP-1/")
    serializer = DailyTripLogSerializer(context={"request": request})
    household = type(
        "HouseholdEvidence",
        (),
        {
            "unique_id": "DTHC-1",
            "status_evidence_image": type(
                "EvidenceImage", (), {"url": "/media/household-proof.jpg"}
            )(),
        },
    )()

    assert serializer._household_status_evidence(household) == [
        {
            "url": "http://testserver/media/household-proof.jpg",
            "household_collection_id": "DTHC-1",
            "trip_household_collection_id": "DTHC-1",
            "image_type": "status_evidence",
        }
    ]
