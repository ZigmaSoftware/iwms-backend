from django.db import models
import uuid
from .utils.comfun import generate_unique_id

def generate_propertyName_id():
    return f"PROPERTY{generate_unique_id()}"

class Property(models.Model):
    """
    Transport Master: Fuel Type
    -----------------------------------
    Defines available fuel types (e.g. Diesel, Petrol, CNG).
    Supports soft delete and active/inactive toggling.
    """
    # Unique identifier for internal and API-level use
    unique_id = models.CharField(
        max_length=40,
        unique=True,
        default=generate_propertyName_id,
        editable=False
    )
    
    # Business fields
    property_name = models.CharField(max_length=100)
    
    # Status flags
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    

    class Meta:
        verbose_name = "Fuel Type"
        verbose_name_plural = "Fuel Types"
        ordering = ["property_name"]

    def __str__(self):
        return self.property_name

    # Soft delete override
    def delete(self, *args, **kwargs):
        """
        Soft delete: marks record as deleted without physically removing it.
        """
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
