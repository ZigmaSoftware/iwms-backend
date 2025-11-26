from django.db import models
from .utils.comfun import generate_unique_id

def generate_continent_id():
    return f"CONT{generate_unique_id()}"

class Continent(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_continent_id
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        """
        Soft delete – mark continent as deleted.
        Do NOT change is_active here. Status toggle uses is_active.
        """
        self.is_delete = True
        self.save(update_fields=["is_delete"])
