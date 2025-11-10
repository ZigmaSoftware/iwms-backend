
from django.db import models
from .utils.comfun import generate_unique_id

def generate_user_type_id():
    """Generate a unique ID prefixed with USRTYPE."""
    return f"USRTYPE{generate_unique_id()}"

class UserType(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_user_type_id,
        editable=False
    )
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        verbose_name = "User Type"
        verbose_name_plural = "User Types"

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        """
        Soft delete: mark this user type as inactive (and optionally cascade).
        """
        self.is_active = False
        self.is_delete = True
        self.save(update_fields=["is_active", "is_delete"])

        # If you have related users, you can optionally deactivate them here
        related_users = getattr(self, "users", None)
        if related_users is not None:
            for user in related_users.all():
                user.is_active = False
                user.save(update_fields=["is_active"])

