from django.db import models

from .utils.comfun import generate_unique_id
from .userType import UserType  # since you already have this
from .staffUserType import StaffUserType
from .customercreation import CustomerCreation
from .district import District
from .city import City
from .zone import Zone
from .ward import Ward
from .staffcreation import StaffOfficeDetails
def generate_user_id():
    # Prepend USER- to the unique ID
    return f"USER{generate_unique_id()}"


class User(models.Model):
    unique_id = models.CharField(max_length=100, unique=True, default=generate_user_id)

    user_type = models.ForeignKey(UserType, on_delete=models.SET_NULL, null=True, related_name="users")

    password = models.CharField(max_length=128)

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

    customer_id = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        related_name="users_customer"
    )

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

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)


    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.unique_id} ({self.user_type.name if self.user_type else 'No Type'})"