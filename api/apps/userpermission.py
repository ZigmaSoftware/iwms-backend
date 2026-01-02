
from django.db import models
from .utils.comfun import generate_unique_id
from .mainuserscreen import MainUserScreen
from .userscreen import UserScreen
from .userType import UserType


def generate_userpermission_id():
    """Generate a unique ID prefixed with UPRM."""
    return f"UPRM{generate_unique_id()}"


class UserPermission(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_userpermission_id
    )

    user_type = models.ForeignKey(
        UserType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_permissions"
    )

    main_screen = models.ForeignKey(
        MainUserScreen,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="main_user_permissions"
    )

    user_screen = models.ForeignKey(
        UserScreen,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_permissions"
    )

    permissions = models.JSONField(default=dict)

    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        unique_together = ("user_type", "main_screen", "user_screen")

    def __str__(self):
        main = self.main_screen.mainscreen if self.main_screen else "No Main Screen"
        screen = self.user_screen.screen_name if self.user_screen else "No Screen"
        usertype = self.user_type.name if self.user_type else "No User Type"
        return f"{usertype} → {main} / {screen}"

    def delete(self, *args, **kwargs):
        """Soft delete instead of removing the record."""
        self.is_active = False
        self.is_delete = True
        self.save(update_fields=["is_active", "is_delete"])
