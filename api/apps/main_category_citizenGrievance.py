from django.db import models
from .utils.comfun import generate_unique_id


def generate_maincategory_id():
    """Generate a unique ID prefixed with CMPMC"""
    return f"CMPMC{generate_unique_id()}"


class MainCategory(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_maincategory_id,
        editable=False
    )

    main_categoryName = models.CharField(
        max_length=100,
        unique=True,
      
    )

    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        verbose_name = "Main Category"
        verbose_name_plural = "Main Categories"

    def __str__(self):
        return self.main_categoryName

    def delete(self, *args, **kwargs):
        """Soft Delete – same logic as UserType"""
        self.is_active = False
        self.is_delete = True
        self.save(update_fields=["is_active", "is_delete"])
