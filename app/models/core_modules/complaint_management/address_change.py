"""Change-Address request linked 1:1 to a complaint ticket.

Ported from the government backend. The proposed-address geo FKs follow this
project's model (state/district/panchayat/zone/ward) instead of government's
AreaType + local-body hierarchy, which does not exist here.
"""

from django.conf import settings
from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


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

    ticket_id = models.CharField(max_length=30, null=True, blank=True)
    customer_id = models.CharField(max_length=30, null=True, blank=True)

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

    new_state_id = models.CharField(max_length=30, null=True, blank=True)
    new_district_id = models.CharField(max_length=30, null=True, blank=True)
    new_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    new_zone_id = models.CharField(max_length=30, null=True, blank=True)
    new_ward_id = models.CharField(max_length=30, null=True, blank=True)

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
    verified_by = models.CharField(max_length=30, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_remarks = models.TextField(null=True, blank=True)

    approved_by = models.CharField(max_length=30, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("complaint_address_change_request_list", "complaint_address_change_request_detail")

    class Meta:
        ordering = ["-created"]
        verbose_name = "Complaint Address Change Request"
        verbose_name_plural = "Complaint Address Change Requests"

    def __str__(self):
        return f"{self.ticket_id} address change"

    @property
    def ticket(self):
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket
        if self.ticket_id:
            return ComplaintTicket.objects.filter(unique_id=self.ticket_id).first()
        return None

    @property
    def customer(self):
        from app.models.masters.customer_masters.customercreation import CustomerCreation
        if self.customer_id:
            return CustomerCreation.objects.filter(unique_id=self.customer_id).first()
        return None

    @property
    def new_state(self):
        from app.models.superadmin.common_masters.state import State
        if self.new_state_id:
            return State.objects.filter(unique_id=self.new_state_id).first()
        return None

    @property
    def new_district(self):
        from app.models.masters.district import District
        if self.new_district_id:
            return District.objects.filter(unique_id=self.new_district_id).first()
        return None

    @property
    def new_panchayat(self):
        from app.models.masters.panchayat import Panchayat
        if self.new_panchayat_id:
            return Panchayat.objects.filter(unique_id=self.new_panchayat_id).first()
        return None

    @property
    def new_zone(self):
        from app.models.masters.zone import Zone
        if self.new_zone_id:
            return Zone.objects.filter(unique_id=self.new_zone_id).first()
        return None

    @property
    def new_ward(self):
        from app.models.masters.ward import Ward
        if self.new_ward_id:
            return Ward.objects.filter(unique_id=self.new_ward_id).first()
        return None

    @property
    def verified_by_user(self):
        from django.conf import settings
        if self.verified_by:
            return settings.AUTH_USER_MODEL.objects.filter(unique_id=self.verified_by).first()
        return None

    @property
    def approved_by_user(self):
        from django.conf import settings
        if self.approved_by:
            return settings.AUTH_USER_MODEL.objects.filter(unique_id=self.approved_by).first()
        return None