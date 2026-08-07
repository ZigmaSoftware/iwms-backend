"""Change-Address request linked 1:1 to a complaint ticket.

Ported from the government backend. The proposed-address geo FKs follow this
project's model (state/district/panchayat/zone/ward) instead of government's
AreaType + local-body hierarchy, which does not exist here.
"""

from django.conf import settings
from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.customers.customercreation import CustomerCreation
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward
from app.models.complaint_management.ticket import ComplaintTicket


def generate_address_change_id():
    return f"CPTADR-{generate_unique_id()}"


def address_proof_upload_path(instance, filename):
    return f"uploads/complaint_address_proof/{instance.unique_id}_{filename}"


class ComplaintAddressChangeRequest(BaseMaster):
    """Change-Address request linked 1:1 to a ticket.

    On approval the linked CustomerCreation address is overwritten in place
    (no address-history table per project decision).
    """

    class ChangeType(models.TextChoices):
        SERVICE_ADDRESS_CHANGE = "SERVICE_ADDRESS_CHANGE", "Service Address Change"
        BILLING_ADDRESS_CHANGE = "BILLING_ADDRESS_CHANGE", "Billing Address Change"
        ADDRESS_CORRECTION = "ADDRESS_CORRECTION", "Address Correction"
        WARD_ROUTE_CHANGE = "WARD_ROUTE_CHANGE", "Ward / Route Change"

    class VerificationStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"

    class ProofType(models.TextChoices):
        AADHAAR = "AADHAAR_ADDRESS_PROOF", "Aadhaar Address Proof"
        EB_BILL = "EB_BILL", "Electricity Bill"
        WATER_TAX = "WATER_TAX_RECEIPT", "Water Tax Receipt"
        PROPERTY_TAX = "PROPERTY_TAX_RECEIPT", "Property Tax Receipt"
        RENT_AGREEMENT = "RENT_AGREEMENT", "Rent Agreement"
        OWNER_DECLARATION = "OWNER_DECLARATION", "Owner Declaration"
        OTHER = "OTHER_PROOF", "Other Proof"

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_address_change_id,
        editable=False,
    )

    ticket = models.OneToOneField(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="address_change_request",
    )
    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.PROTECT,
        related_name="address_change_requests",
    )

    change_type = models.CharField(
        max_length=40,
        choices=ChangeType.choices,
        default=ChangeType.SERVICE_ADDRESS_CHANGE,
    )

    old_address_snapshot = models.JSONField(null=True, blank=True)

    new_building_no = models.CharField(max_length=20, null=True, blank=True)
    new_street = models.CharField(max_length=100, null=True, blank=True)
    new_area = models.CharField(max_length=50, null=True, blank=True)
    new_landmark = models.CharField(max_length=200, null=True, blank=True)
    new_pincode = models.CharField(max_length=10, null=True, blank=True)
    new_latitude = models.CharField(max_length=100, null=True, blank=True)
    new_longitude = models.CharField(max_length=100, null=True, blank=True)
    new_full_address = models.TextField(null=True, blank=True)

    new_state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="address_change_requests",
        db_column="new_state_id",
    )
    new_district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="address_change_requests",
        db_column="new_district_id",
    )
    new_panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="address_change_requests",
        db_column="new_panchayat_id",
    )
    new_zone = models.ForeignKey(
        Zone,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="address_change_requests",
        db_column="new_zone_id",
    )
    new_ward = models.ForeignKey(
        Ward,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="address_change_requests",
        db_column="new_ward_id",
    )

    proof_type = models.CharField(
        max_length=40,
        choices=ProofType.choices,
        null=True,
        blank=True,
    )
    proof_file = models.FileField(
        upload_to=address_proof_upload_path,
        null=True,
        blank=True,
    )

    requested_effective_date = models.DateField(null=True, blank=True)

    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_address_changes",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_remarks = models.TextField(null=True, blank=True)

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_address_changes",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Complaint Address Change Request"
        verbose_name_plural = "Complaint Address Change Requests"

    def __str__(self):
        return f"{self.ticket_id} address change"
