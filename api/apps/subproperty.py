from django.db import models
from .utils.comfun import generate_unique_id
from .property import Property  # import parent Property model


def generate_subproperty_id():
    """Generate prefixed SubProperty ID for traceability."""
    return f"SUBPROPERTY-{generate_unique_id()}"


class SubProperty(models.Model):
    """
    Master: SubProperty
    -----------------------------------
    Defines sub-properties linked to a main Property.
    Supports soft delete and active/inactive toggling.
    """

    # Unique identifier for internal and API-level use
    unique_id = models.CharField(
        max_length=40,
        unique=True,
        default=generate_subproperty_id,
        editable=False
    )

    # Relationship to parent Property
    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="sub_properties"
    )

    # Business field
    sub_property_name = models.CharField(max_length=100)

    # Status flags
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Sub Property"
        verbose_name_plural = "Sub Properties"
        ordering = ["sub_property_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "sub_property_name"],
                condition=models.Q(is_deleted=False),
                name="unique_sub_property_per_property_not_deleted"
            )
        ]

    def __str__(self):
        return f"{self.sub_property_name} ({self.property.property_name})"

    def delete(self, *args, **kwargs):
        """Soft delete without removing the record."""
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
