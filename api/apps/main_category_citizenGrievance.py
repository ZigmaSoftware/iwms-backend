from django.db import models
from .utils.comfun import generate_unique_id

def generate_maincategory_id():
    # Prepend CONT- to the unique ID
    return f"CMPMC{generate_unique_id()}"

class MainCategory(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default= generate_maincategory_id
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False) 

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        """Soft delete: deactivate this maincategory and its related subcategory."""
        self.is_active = False
        self.save(update_fields=["is_active"])

        # Deactivate all related category (if relation exists)
        related_subcategory = getattr(self, "subcategory", None)
        if related_subcategory is not None:
            for subcategory in related_subcategory.all():
                subcategory.is_active = False
                subcategory.save(update_fields=["is_active"])
