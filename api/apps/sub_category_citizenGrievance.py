from django.db import models
from .main_category_citizenGrievance import MainCategory

from .utils.comfun import generate_unique_id

def generate_subcategory_id():
    # Prepend COUNTRY- to the unique ID
    return f"CMPSC{generate_unique_id()}"

class SubCategory(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default= generate_subcategory_id
    )
    mainCategory = models.ForeignKey(
        MainCategory,
        on_delete=models.PROTECT,
        related_name='subCategory'
    )
    name = models.CharField(max_length=100)
    currency = models.CharField(max_length=20, blank=True, null=True)
    mob_code = models.CharField(max_length=5, blank=True, null=True)       # e.g. +91
    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)


    class Meta:
        verbose_name_plural = "subCategories"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.currency  or ''})".strip()

    def delete(self, *args, **kwargs):
        """
        Soft delete:
        - Mark this subcat inactive.
        - Mark all related subcategories inactive (if relationships exist).
        """
        self.is_active = False
        self.save(update_fields=["is_active"])

