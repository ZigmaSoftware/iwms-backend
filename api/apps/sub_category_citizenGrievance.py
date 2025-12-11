from django.db import models
from api.apps.main_category_citizenGrievance import MainCategory
from api.apps.utils.comfun import generate_unique_id


def generate_subcategory_id():
    return f"CMPSC{generate_unique_id()}"


class SubCategory(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_subcategory_id
    )

    mainCategory = models.ForeignKey(
        MainCategory,
        on_delete=models.PROTECT,
        related_name='sub_categories'
    )

    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        self.is_delete = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
