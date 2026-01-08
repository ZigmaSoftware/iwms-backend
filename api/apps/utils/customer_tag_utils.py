import json
import qrcode
from io import BytesIO

from django.core.files.base import ContentFile

from api.apps.customer_tag import CustomerTag


# --------------------------------------------------
# CUSTOMER TAG CODE GENERATOR (DETERMINISTIC)
# --------------------------------------------------
def generate_customer_tag_code(
    city_code: str,
    ward_code: str,
) -> str:
    """
    Generates admin-readable, deterministic tag codes.

    Format:
        CT-CHN-W01-000001

    city_code : first 3 letters of city
    ward_code : numeric or short ward identifier (string-safe)
    """

    city_code = city_code.upper()
    ward_code = str(ward_code).zfill(2)

    prefix = f"CT-{city_code}-W{ward_code}"

    last_tag = (
        CustomerTag.objects
        .filter(tag_code__startswith=prefix)
        .order_by("-tag_code")
        .values_list("tag_code", flat=True)
        .first()
    )

    if last_tag:
        last_seq = int(last_tag.split("-")[-1])
        next_seq = last_seq + 1
    else:
        next_seq = 1

    return f"{prefix}-{next_seq:06d}"


# --------------------------------------------------
# CUSTOMER HOUSEHOLD QR GENERATOR
# --------------------------------------------------
def generate_customer_qr(payload: dict) -> ContentFile:
    """
    Generates a QR image with JSON payload.
    Stored under media/customer_qr/

    Payload example:
    {
        "v": 1,
        "type": "HOUSEHOLD",
        "customer_id": "CUS-XXXX",
        "tag_code": "CT-CHN-W01-000001",
        "zone": "Zone 1",
        "ward": "Ward 1"
    }
    """

    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_Q,
        box_size=8,
        border=2,
    )

    qr.add_data(json.dumps(payload, separators=(",", ":")))
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    filename = f"{payload.get('tag_code')}.png"
    return ContentFile(buffer.read(), name=filename)
