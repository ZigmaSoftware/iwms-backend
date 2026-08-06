"""Public grievance intake API — no login, no module permission requirement.

Ported from the government backend's `PublicGrievanceViewSet`
(`citizen_viewset.py`), adapted for this project's geo model
(state/district/panchayat/zone/ward under Company/Project tenancy, instead
of government's State/District + five local-body masters) and the absence
of a `waste_types` M2M on `ComplaintTicket` here — category/subcategory is
this project's only complaint-type axis, so the waste-type-driven
priority/team/SLA branch on the government side has no equivalent; routing
is entirely `apply_routing_and_sla` (category + geo + priority).

Registered at `publicgrievance` with `authentication_classes = []` and
`permission_classes = [AllowAny]`. Because `ComplaintTicketViewSet` (the
staff-facing API) is scoped to the caller's company/project via
`CompanyScopedViewSet`, a ticket created here MUST be stamped with a
company/project or it will silently disappear from every supervisor's list.
There is no logged-in citizen to take that from here, so it resolves from
the chosen geo (panchayat/zone/ward all carry a company/project) and falls
back to the single active Company/Project when the deployment only has one
— true multi-tenant public intake (letting the citizen pick a company) is
out of scope until this project actually has more than one live tenant.
"""

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from rest_framework import status as http_status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.complaint_management import (
    ComplaintAttachment,
    ComplaintCategory,
    ComplaintPriority,
    ComplaintSource,
    ComplaintStatus,
    ComplaintStatusHistory,
    ComplaintSubcategory,
    ComplaintTicket,
)
from app.services.complaint_ticket_routing import apply_routing_and_sla


def _decimal_from_input(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_company_project(*, panchayat, zone, ward, state, district):
    """Best-effort company/project for an anonymous submission.

    Prefers whichever chosen geo node actually carries a company/project
    (ward -> zone -> panchayat, closest to the citizen's pick first), then
    falls back to the single active Company/Project when the deployment
    has exactly one — the common case while this project has one tenant.
    """
    for node in (ward, zone, panchayat):
        if node is None:
            continue
        company_id = getattr(node, "company_id_id", None)
        project_id = getattr(node, "project_id_id", None)
        if company_id and project_id:
            return company_id, project_id

    companies = list(Company.objects.filter(is_deleted=False, is_active=True)[:2])
    if len(companies) == 1:
        company = companies[0]
        projects = list(
            Project.objects.filter(
                company_id=company, is_deleted=False, is_active=True
            )[:2]
        )
        if len(projects) == 1:
            return company.unique_id, projects[0].unique_id
    return None, None


class PublicGrievanceViewSet(viewsets.ViewSet):
    """Public grievance intake API with no login or module permission requirement."""

    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    @action(detail=False, methods=["get"])
    def meta(self, request):
        categories = ComplaintCategory.objects.filter(is_deleted=False, is_active=True).order_by("sort_order")
        subcategories = ComplaintSubcategory.objects.filter(
            is_deleted=False, is_active=True, category__is_deleted=False, category__is_active=True
        ).order_by("sort_order")
        return Response({
            "categories": [
                {"unique_id": c.unique_id, "category_name": c.category_name}
                for c in categories
            ],
            "subcategories": [
                {"unique_id": s.unique_id, "category": s.category_id, "subcategory_name": s.subcategory_name}
                for s in subcategories
            ],
        })

    # ---- GET /publicgrievance/states/ ----
    # Read-only, name-only passthroughs onto the flat geo masters so the
    # public form can offer a state/district/panchayat picker without a
    # login (the real /common-masters/ and /masters/ APIs are behind auth).
    @action(detail=False, methods=["get"])
    def states(self, request):
        rows = State.objects.filter(is_deleted=False, is_active=True).order_by("name")
        return Response([{"unique_id": s.unique_id, "name": s.name} for s in rows])

    # ---- GET /publicgrievance/districts/?state=<state id> ----
    @action(detail=False, methods=["get"])
    def districts(self, request):
        rows = District.objects.filter(is_deleted=False, is_active=True)
        state_id = request.query_params.get("state")
        if state_id:
            rows = rows.filter(state_id=state_id)
        rows = rows.order_by("name")
        return Response([
            {"unique_id": d.unique_id, "name": d.name, "state_id": d.state_id_id}
            for d in rows
        ])

    # ---- GET /publicgrievance/panchayats/?district=<district id> ----
    @action(detail=False, methods=["get"])
    def panchayats(self, request):
        district_id = request.query_params.get("district")
        if not district_id:
            return Response([])
        rows = Panchayat.objects.filter(
            is_deleted=False, is_active=True, district_id=district_id
        ).order_by("panchayat_name")
        return Response([
            {"unique_id": p.unique_id, "name": p.panchayat_name}
            for p in rows
        ])

    # ---- GET /publicgrievance/wards/?panchayat=<panchayat id> ----
    @action(detail=False, methods=["get"])
    def wards(self, request):
        panchayat_id = request.query_params.get("panchayat")
        if not panchayat_id:
            return Response([])
        rows = Ward.objects.filter(
            is_deleted=False, is_active=True, panchayat_id=panchayat_id
        ).order_by("ward_name")
        return Response([
            {"unique_id": w.unique_id, "name": w.ward_name, "zone_id": w.zone_id_id}
            for w in rows
        ])

    @transaction.atomic
    def create(self, request):
        data = request.data
        person_name = str(data.get("person_name") or data.get("profile_name") or "").strip()
        description = str(data.get("description") or "").strip()
        location_text = str(data.get("location_text") or "").strip()
        device_id = str(data.get("device_id") or "").strip()
        phone = str(data.get("phone") or data.get("wa_phone") or "").strip()
        email = str(data.get("email") or "").strip()
        gender = str(data.get("gender") or "").strip().lower()
        if gender not in dict(ComplaintTicket.GENDER_CHOICES):
            gender = ""
        latitude = _decimal_from_input(data.get("latitude"))
        longitude = _decimal_from_input(data.get("longitude"))

        if email:
            try:
                validate_email(email)
            except ValidationError:
                return Response({"email": "Enter a valid email address."}, status=http_status.HTTP_400_BAD_REQUEST)

        if not person_name:
            return Response({"person_name": "This field is required."}, status=http_status.HTTP_400_BAD_REQUEST)
        if not description:
            return Response({"description": "This field is required."}, status=http_status.HTTP_400_BAD_REQUEST)
        if latitude is None or longitude is None:
            return Response({"location": "Latitude and longitude are required."}, status=http_status.HTTP_400_BAD_REQUEST)

        # Complaint Type / Sub-Type chosen on the public form.
        selected_category = ComplaintCategory.objects.filter(
            unique_id=data.get("category"), is_deleted=False, is_active=True
        ).first()
        subcategory = ComplaintSubcategory.objects.filter(
            unique_id=data.get("subcategory"), is_deleted=False, is_active=True
        ).first()
        if subcategory and (not selected_category or subcategory.category_id != selected_category.unique_id):
            subcategory = None

        if not selected_category:
            return Response(
                {"category": "Select a complaint type."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # Flat geo chosen on the public form: State -> District -> Panchayat -> Ward.
        state = State.objects.filter(unique_id=data.get("state"), is_deleted=False).first()
        district = District.objects.filter(unique_id=data.get("district"), is_deleted=False).first()
        panchayat = Panchayat.objects.filter(unique_id=data.get("panchayat"), is_deleted=False).first()
        ward = Ward.objects.filter(unique_id=data.get("ward"), is_deleted=False).first()
        zone = ward.zone_id if ward else None
        if panchayat and not district:
            district = panchayat.district_id
        if district and not state:
            state = district.state_id

        category = selected_category or ComplaintCategory.objects.filter(
            category_code="OTHER", is_deleted=False, is_active=True
        ).first()
        if not category:
            category = ComplaintCategory.objects.filter(is_deleted=False, is_active=True).order_by("sort_order").first()
        if not category:
            return Response(
                {"detail": "Complaint categories are not configured. Run the complaint-ticket seeder."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        priority = (
            (subcategory.default_priority if subcategory else None)
            or category.default_priority
            or ComplaintPriority.objects.filter(priority_code="P3", is_deleted=False).first()
        )
        status_obj = ComplaintStatus.objects.filter(status_code="SUBMITTED", is_deleted=False).first()
        if not priority or not status_obj:
            return Response(
                {"detail": "Complaint ticket masters are not configured. Run the complaint-ticket seeder."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        company_id, project_id = _resolve_company_project(
            panchayat=panchayat, zone=zone, ward=ward, state=state, district=district,
        )

        # The device key is still stored on the ticket for traceability. No
        # duplicate-submission cooldown is enforced — a citizen can register
        # multiple complaints from one device (mirrors government, which
        # ships this disabled too).
        idempotency_key = f"publicgrievance:{device_id}" if device_id else None

        source, _ = ComplaintSource.objects.get_or_create(
            source_code="PUBLIC_GRIEVANCE",
            defaults={"source_name": "Public Grievance", "is_active": True, "is_deleted": False},
        )
        ticket = ComplaintTicket.objects.create(
            company_id_id=company_id,
            project_id_id=project_id,
            source=source,
            category=category,
            subcategory=subcategory,
            priority=priority,
            status=status_obj,
            profile_name=person_name,
            wa_phone=phone or None,
            email=email or None,
            gender=gender or None,
            title=(description or (subcategory.subcategory_name if subcategory else "") or category.category_name)[:120],
            description=description,
            location_text=location_text,
            latitude=latitude,
            longitude=longitude,
            state=state,
            district=district,
            panchayat=panchayat,
            zone=zone,
            ward=ward,
            idempotency_key=idempotency_key,
        )
        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=None,
            to_status=status_obj,
            changed_by_system=True,
            remarks="Raised via public grievance form",
            visible_to_citizen=True,
        )

        photo = request.FILES.get("photo") or request.FILES.get("file")
        if photo:
            ComplaintAttachment.objects.create(
                ticket=ticket,
                file=photo,
                file_name=getattr(photo, "name", None),
                file_type="photo",
                mime_type=getattr(photo, "content_type", None),
                file_size=getattr(photo, "size", None),
            )

        apply_routing_and_sla(ticket, save=True)

        return Response(
            {
                "message": "Public grievance submitted successfully.",
                "ticket_no": ticket.ticket_no,
                "unique_id": ticket.unique_id,
            },
            status=http_status.HTTP_201_CREATED,
        )

    # ---- GET /publicgrievance/status/?ticket_no=... or ?mobile=... ----
    @action(detail=False, methods=["get"])
    def status(self, request):
        ticket_no = str(request.query_params.get("ticket_no") or "").strip()
        mobile = str(request.query_params.get("mobile") or "").strip()
        if not ticket_no and not mobile:
            return Response(
                {"detail": "Provide a ticket number or mobile number."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        qs = (
            ComplaintTicket.objects.filter(is_deleted=False)
            .select_related("status", "category", "subcategory")
            .prefetch_related("status_history", "status_history__to_status")
        )
        qs = qs.filter(ticket_no__iexact=ticket_no) if ticket_no else qs.filter(wa_phone=mobile)
        tickets = list(qs.order_by("-created")[:20])
        if not tickets:
            return Response({"detail": "No grievance found."}, status=http_status.HTTP_404_NOT_FOUND)

        def timeline_for(ticket):
            entries = [h for h in ticket.status_history.all() if h.visible_to_citizen]
            entries.sort(key=lambda h: h.changed_at)
            return [
                {
                    "status": h.to_status.status_name if h.to_status else None,
                    "status_code": h.to_status.status_code if h.to_status else None,
                    "at": h.changed_at,
                    "remarks": h.remarks or "",
                }
                for h in entries
            ]

        return Response([
            {
                "ticket_no": t.ticket_no,
                "status": t.status.status_name if t.status else None,
                "status_code": t.status.status_code if t.status else None,
                "category": t.category.category_name if t.category else None,
                "subcategory": t.subcategory.subcategory_name if t.subcategory else None,
                "description": t.description,
                "location_text": t.location_text,
                "created": t.created,
                "timeline": timeline_for(t),
            }
            for t in tickets
        ])
