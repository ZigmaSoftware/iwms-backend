from django.db import models

from .utils.comfun import generate_unique_id
from .userType import UserType
from .staffUserType import StaffUserType
from .customercreation import CustomerCreation
from .district import District
from .city import City
from .zone import Zone
from .ward import Ward
from .staffcreation import StaffOfficeDetails


def generate_user_id():
    return f"USER{generate_unique_id()}"


class User(models.Model):

    # -----------------------------
    # Core User Identity
    # -----------------------------
    unique_id = models.CharField(
        max_length=100,
        unique=True,
        default=generate_user_id
    )

    user_type = models.ForeignKey(
        UserType,
        on_delete=models.SET_NULL,
        null=True,
        related_name="users"
    )

    password = models.CharField(max_length=128)

    # -----------------------------
    # STAFF-RELATED FIELDS
    # -----------------------------
    staffusertype_id = models.ForeignKey(
        StaffUserType,
        on_delete=models.SET_NULL,
        null=True,
        related_name="users_staff_usertype"
    )

    staff_id = models.ForeignKey(
        StaffOfficeDetails,
        on_delete=models.SET_NULL,
        null=True,
        related_name="users_staff"
    )

    # -----------------------------
    # CUSTOMER-RELATED FIELD
    # -----------------------------
    customer_id = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        related_name="users_customer"
    )

    # -----------------------------
    # LOCATION FIELDS
    # -----------------------------
    district_id = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        related_name="users_district"
    )

    city_id = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        related_name="users_city"
    )

    zone_id = models.ForeignKey(
        Zone,
        on_delete=models.SET_NULL,
        null=True,
        related_name="users_zone"
    )

    ward_id = models.ForeignKey(
        Ward,
        on_delete=models.SET_NULL,
        null=True,
        related_name="users_ward"
    )

    # -----------------------------
    # SYSTEM FIELDS
    # -----------------------------
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["-id"]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        user_type = self.user_type.name if self.user_type else "No Type"
        return f"{self.unique_id} ({user_type})"
