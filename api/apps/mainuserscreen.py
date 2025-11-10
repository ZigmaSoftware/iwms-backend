
from django.db import models
from .utils.comfun import generate_unique_id

def generate_mainuserscreen_id():
    """Generate a unique ID prefixed with MNSCRN."""
    return f"MNSCRN{generate_unique_id()}"

class MainUserScreen(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_mainuserscreen_id
    )
    mainscreen = models.CharField(max_length=150, unique=True)
    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        verbose_name = "Main User Screen"
        verbose_name_plural = "Main User Screens"

    def __str__(self):
        return self.mainscreen

    def delete(self, *args, **kwargs):
        """Soft delete: deactivate this main user screen and optionally cascade."""
        self.is_active = False
        self.is_delete = True
        self.save(update_fields=["is_active", "is_delete"])

        # Optional: Deactivate related modules or screens (if relation exists)
        related_modules = getattr(self, "modules", None)
        if related_modules is not None:
            for module in related_modules.all():
                module.is_active = False
                module.save(update_fields=["is_active"])
