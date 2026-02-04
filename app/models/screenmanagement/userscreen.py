from django.db import models
from app.utils.tenancy import CompanyProjectMixin
from app.utils.comfun import generate_unique_id
from .mainscreen import MainScreen


def generate_userscreen_id():
    return f"USERSCREEN-{generate_unique_id()}"


class UserScreen(CompanyProjectMixin, models.Model):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_userscreen_id,
        editable=False
    )

    mainscreen_id = models.ForeignKey(
        MainScreen,
        on_delete=models.PROTECT,
        related_name="userscreens",
        to_field="unique_id",
        db_column="mainscreen_id"
    )

    userscreen_name = models.CharField(max_length=50, unique=True)
    folder_name = models.CharField(max_length=50, unique=True)
    icon_name = models.CharField(max_length=50, unique=True)

    # REMOVE unique=True
    order_no = models.IntegerField()

    description = models.CharField(max_length=255, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    

    class Meta:
        ordering = ["order_no"]
        verbose_name = "User Screen"
        verbose_name_plural = "User Screens"
        constraints = [
            models.UniqueConstraint(
                fields=["mainscreen_id", "order_no"],
                name="unique_order_per_mainscreen"
            ),
        ]

    def __str__(self):
        return self.userscreen_name

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])
