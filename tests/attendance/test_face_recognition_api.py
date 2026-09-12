"""End-to-end attendance face tests against the real HTTP endpoints.

Ported from iwms-government-backend's equivalent suite, adapted to this
project's own attendance data model: `Employee` (holds the reference photo +
cached embedding, one-to-one with `Staffcreation`) and `Recognized` (the punch
log) — not government's `Staffcreation.attendance_reg_image` /
`DailyAttendanceReg`. The face_recognition provider package itself is
unmodified and shared verbatim between the two backends.

Real face photos already on disk under media/emp_image/ are used for the
same-person / robustness checks (self-match and a re-encoded copy of the same
photo) rather than trusting any two *different* files to depict different
people — the government backend's registration data turned out to have
several employees mislabelled under one ID, which made an early version of
this exact test look like the model was broken when the fixture data was
actually wrong. Self-match + robustness + a real no-face image is enough to
prove the wiring without needing trustworthy multi-person ground truth here.
"""
import glob
import io

import jwt
import pytest
from django.test import override_settings
from PIL import Image

from app.services import face_recognition as fr


def _reg_photos():
    files = sorted(glob.glob("media/emp_image/*.jpg"))
    assert files, "No reference photos under media/emp_image/ to test against."
    return files


def _bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def _upload(raw, name="face.jpg"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, raw, content_type="image/jpeg")


def _variant(raw):
    """A re-encoded, resized copy of the same photo — stands in for 'same
    person, different capture' without needing a second real photo of them."""
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im = im.resize((int(im.width * 0.8), int(im.height * 0.8)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=70)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _clear_provider_cache():
    fr.reset_provider_cache()
    yield
    fr.reset_provider_cache()


@pytest.fixture
def staff(db, company):
    from app.models.staff_creations.staffcreation import Staffcreation

    return Staffcreation.objects.create(
        employee_name="Face Test User",
        staff_unique_id="STC-FACETEST-1",
        company_id=company,
    )


@override_settings(FACE_RECOGNITION_PROVIDER="insightface")
def test_face_config_reports_active_provider(db, auth_client):
    res = auth_client.get("/api/v1/attendance/face-config/")
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["provider"] == "insightface"
    assert "compreface" in body["available_providers"]
    assert body["ready"] is True


@override_settings(FACE_RECOGNITION_PROVIDER="compreface")
def test_face_config_switches_with_the_setting(db, auth_client):
    body = auth_client.get("/api/v1/attendance/face-config/").json()
    assert body["provider"] == "compreface"
    # Each provider carries its own scale — this is the value the old
    # hardcoded 0.95 check used.
    assert body["threshold"] == 0.95


@override_settings(FACE_RECOGNITION_PROVIDER="insightface")
def test_face_config_requires_auth_like_register_and_recognize(db, api_client):
    """Unlike the government backend (where face-config is public), this
    project routes it through AUTH_ONLY_SUFFIXES alongside register/recognize
    — matching how this backend has always treated that pair, rather than
    copying government's choice wholesale."""
    res = api_client.get("/api/v1/attendance/face-config/")
    assert res.status_code == 401


@override_settings(FACE_RECOGNITION_PROVIDER="insightface")
def test_register_then_recognize_same_person_marks_attendance(staff, auth_client):
    from app.models.staff_creations.attendance import Employee

    photos = _reg_photos()

    res = auth_client.post(
        "/api/v1/attendance/register/",
        {"emp_id": staff.staff_unique_id, "source_image": _upload(_bytes(photos[0]))},
        format="multipart",
    )
    assert res.status_code == 200, res.content
    assert res.json()["provider"] == "insightface"

    employee = Employee.objects.get(staff=staff)
    # The embedding must be cached at registration so a punch only has to
    # process the incoming selfie.
    assert employee.face_embedding and len(employee.face_embedding) == 512

    res = auth_client.post(
        "/api/v1/attendance/recognize/",
        {"emp_id": staff.staff_unique_id, "name": staff.employee_name,
         "latitude": "12.9", "longitude": "77.6",
         "captured_image": _upload(_variant(_bytes(photos[0])))},
        format="multipart",
    )
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["punch_type"] == "IN"
    assert body["score"] > body["threshold"]


@override_settings(FACE_RECOGNITION_PROVIDER="insightface")
def test_second_punch_toggles_to_out(staff, auth_client):
    photos = _reg_photos()
    auth_client.post(
        "/api/v1/attendance/register/",
        {"emp_id": staff.staff_unique_id, "source_image": _upload(_bytes(photos[0]))},
        format="multipart",
    )

    def punch():
        return auth_client.post(
            "/api/v1/attendance/recognize/",
            {"emp_id": staff.staff_unique_id, "name": staff.employee_name,
             "latitude": "12.9", "longitude": "77.6",
             "captured_image": _upload(_variant(_bytes(photos[0])))},
            format="multipart",
        )

    assert punch().json()["punch_type"] == "IN"
    assert punch().json()["punch_type"] == "OUT"


@override_settings(FACE_RECOGNITION_PROVIDER="insightface")
def test_register_rejects_an_image_with_no_face(staff, auth_client):
    from app.models.staff_creations.attendance import Employee

    blank = io.BytesIO()
    Image.new("RGB", (400, 400), "white").save(blank, "JPEG")
    res = auth_client.post(
        "/api/v1/attendance/register/",
        {"emp_id": staff.staff_unique_id, "source_image": _upload(blank.getvalue())},
        format="multipart",
    )
    assert res.status_code == 400
    assert "No face detected" in res.json()["error"]
    # A rejected photo must not become the reference — no Employee row at all.
    assert not Employee.objects.filter(staff=staff).exists()


@override_settings(FACE_RECOGNITION_PROVIDER="insightface")
def test_recognize_404s_when_employee_never_registered(staff, auth_client):
    res = auth_client.post(
        "/api/v1/attendance/recognize/",
        {"emp_id": staff.staff_unique_id, "name": staff.employee_name,
         "latitude": "12.9", "longitude": "77.6",
         "captured_image": _upload(_bytes(_reg_photos()[0]))},
        format="multipart",
    )
    assert res.status_code == 404
    assert res.json()["error"] == "Employee not registered"


@override_settings(FACE_RECOGNITION_PROVIDER="insightface")
def test_punch_backfills_embedding_for_employee_enrolled_under_compreface(staff, auth_client):
    """Employees registered while CompreFace was active have a reference
    image but no embedding; the first punch must derive and cache one rather
    than fail."""
    from app.models.staff_creations.attendance import Employee

    photos = _reg_photos()
    auth_client.post(
        "/api/v1/attendance/register/",
        {"emp_id": staff.staff_unique_id, "source_image": _upload(_bytes(photos[0]))},
        format="multipart",
    )

    employee = Employee.objects.get(staff=staff)
    employee.face_embedding = None  # simulate the pre-InsightFace state
    employee.save(update_fields=["face_embedding"])

    res = auth_client.post(
        "/api/v1/attendance/recognize/",
        {"emp_id": staff.staff_unique_id, "name": staff.employee_name,
         "latitude": "12.9", "longitude": "77.6",
         "captured_image": _upload(_variant(_bytes(photos[0])))},
        format="multipart",
    )
    assert res.status_code == 200, res.content
    employee.refresh_from_db()
    assert employee.face_embedding and len(employee.face_embedding) == 512


# ---------------------------------------------------------------------------
# CompreFace path
#
# The hosted API is not reachable from tests, so its HTTP call is stubbed and
# what is asserted is that the *wiring* is intact: the provider is selected,
# it posts both images to the configured URL with the API key, applies its
# own 0.95 cutoff, and stores no embedding. This is the regression guard for
# "InsightFace work broke the CompreFace option" — the same option management
# explicitly asked to keep.
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


@override_settings(FACE_RECOGNITION_PROVIDER="compreface")
def test_compreface_register_and_punch_still_work(staff, auth_client, monkeypatch):
    import app.services.face_recognition.compre_face as cf
    from app.models.staff_creations.attendance import Employee

    calls = []

    def fake_post(url, headers=None, files=None, timeout=None):
        calls.append({"url": url, "headers": headers, "files": sorted(files)})
        return _FakeResponse(
            {"result": [{"source_image_face": {},
                         "face_matches": [{"similarity": 0.97}]}]}
        )

    monkeypatch.setattr(cf.requests, "post", fake_post)

    photos = _reg_photos()
    res = auth_client.post(
        "/api/v1/attendance/register/",
        {"emp_id": staff.staff_unique_id, "source_image": _upload(_bytes(photos[0]))},
        format="multipart",
    )
    assert res.status_code == 200, res.content
    assert res.json()["provider"] == "compreface"

    employee = Employee.objects.get(staff=staff)
    # CompreFace compares image files on its own server, so nothing is cached.
    assert employee.face_embedding is None

    res = auth_client.post(
        "/api/v1/attendance/recognize/",
        {"emp_id": staff.staff_unique_id, "name": staff.employee_name,
         "latitude": "12.9", "longitude": "77.6",
         "captured_image": _upload(_bytes(photos[0]))},
        format="multipart",
    )
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["provider"] == "compreface"
    assert body["score"] == 0.97
    assert body["threshold"] == 0.95

    assert calls, "CompreFace was never called"
    assert calls[0]["url"].endswith("/api/v1/verification/verify")
    assert calls[0]["headers"]["x-api-key"]
    assert calls[0]["files"] == ["source_image", "target_image"]


@override_settings(FACE_RECOGNITION_PROVIDER="compreface")
def test_compreface_below_threshold_is_rejected(staff, auth_client, monkeypatch):
    import app.services.face_recognition.compre_face as cf

    monkeypatch.setattr(
        cf.requests, "post",
        lambda *a, **k: _FakeResponse(
            {"result": [{"source_image_face": {},
                         "face_matches": [{"similarity": 0.80}]}]}
        ),
    )

    photos = _reg_photos()
    auth_client.post(
        "/api/v1/attendance/register/",
        {"emp_id": staff.staff_unique_id, "source_image": _upload(_bytes(photos[0]))},
        format="multipart",
    )
    res = auth_client.post(
        "/api/v1/attendance/recognize/",
        {"emp_id": staff.staff_unique_id, "name": staff.employee_name,
         "latitude": "12.9", "longitude": "77.6",
         "captured_image": _upload(_bytes(photos[0]))},
        format="multipart",
    )
    assert res.status_code == 400
    assert res.json()["error"] == "Face Similarity Not Matched"


@override_settings(FACE_RECOGNITION_PROVIDER="compreface")
def test_compreface_outage_is_503_not_a_rejected_face(staff, auth_client, monkeypatch):
    """A dead face API must not read as 'your face did not match'."""
    import app.services.face_recognition.compre_face as cf

    def boom(*a, **k):
        raise cf.requests.RequestException("connection refused")

    monkeypatch.setattr(cf.requests, "post", boom)

    res = auth_client.post(
        "/api/v1/attendance/register/",
        {"emp_id": staff.staff_unique_id, "source_image": _upload(_bytes(_reg_photos()[0]))},
        format="multipart",
    )
    assert res.status_code == 503, res.content


# ---------------------------------------------------------------------------
# A real (non-superuser) staff member, end to end.
#
# `auth_client` everywhere above authenticates as a Django superuser, which
# short-circuits the module-permission middleware entirely
# (`if request.user.is_superuser: return None`) — so none of the tests above
# ever exercised the actual per-role permission gate `face-config/` failed
# behind in production. This constructs the same kind of JWT the app itself
# sends (a raw `{"unique_id": staff.staff_unique_id}` token, decoded directly
# by `ModulePermissionMiddleware._authenticate_request` — a different
# mechanism from simplejwt's `AccessToken.for_user`) for an ordinary staff
# member with no StaffAccessConfiguration grants at all, to prove the
# bypass really is unconditional rather than merely "happens to work for an
# account that already has every permission".
# ---------------------------------------------------------------------------

def _staff_token(staff):
    from django.conf import settings

    return jwt.encode({"unique_id": staff.staff_unique_id}, settings.SECRET_KEY, algorithm="HS256")


def test_face_config_works_for_an_ordinary_staff_member_with_no_grants(staff, api_client):
    """The actual bug report: a real staff account, already successfully
    using register/recognize, got 403 on face-config specifically — because
    that account has no StaffAccessConfiguration grant for "face-config" (no
    such grant can exist; see the middleware comment). This staff fixture has
    no StaffAccessConfiguration row at all, which is the strictest version of
    that scenario, and face-config must still succeed.
    """
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_staff_token(staff)}")
    res = api_client.get("/api/v1/attendance/face-config/")
    assert res.status_code == 200, res.content


def test_face_config_still_401s_with_no_token_at_all(db, api_client):
    """The bypass is auth-ONLY, not a public endpoint — it must still refuse
    an unauthenticated caller."""
    res = api_client.get("/api/v1/attendance/face-config/")
    assert res.status_code == 401
