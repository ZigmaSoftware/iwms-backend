from django.db import models

from .utils.comfun import generate_unique_id
from .userType import UserType  # since you already have this
def generate_user_id():
    # Prepend USER- to the unique ID
    return f"USER{generate_unique_id()}"


class User(models.Model):
    unique_id = models.CharField(max_length=100, unique=True,default=generate_user_id)
    user_type = models.ForeignKey(UserType, on_delete=models.SET_NULL, null=True, related_name="users")
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=128)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(unique=True, blank=True, null=True, default=None)


    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.username} ({self.user_type.name if self.user_type else 'No Type'})"
