# =========================================================
# models/screen_managements/userscreencolumn.py
# =========================================================

from django.db import models
from django.apps import apps

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id

from app.models.screen_managements.userscreen import UserScreen


def generate_userscreencolumn_id():
    return f"USCRNCOL-{generate_unique_id()}"


class UserScreenColumn(BaseMaster):

    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        unique=True,
        default=generate_userscreencolumn_id,
        editable=False
    )

    # =====================================================
    # SCREEN LINK
    # =====================================================

    userscreen_id = models.ForeignKey(
        UserScreen,
        on_delete=models.CASCADE,
        related_name="screen_columns",
        to_field="unique_id",
        db_column="userscreen_id"
    )

    # =====================================================
    # DJANGO FIELD DETAILS
    # =====================================================

    column_name = models.CharField(
        max_length=100
    )

    verbose_name = models.CharField(
        max_length=150,
        null=True,
        blank=True
    )

    data_type = models.CharField(
        max_length=100
    )

    max_length = models.IntegerField(
        null=True,
        blank=True
    )

    default_value = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    # =====================================================
    # FIELD FLAGS
    # =====================================================

    is_required = models.BooleanField(
        default=False
    )

    is_nullable = models.BooleanField(
        default=True
    )

    is_unique = models.BooleanField(
        default=False
    )

    is_primary_key = models.BooleanField(
        default=False
    )

    is_foreign_key = models.BooleanField(
        default=False
    )

    # =====================================================
    # UI FLAGS
    # =====================================================

    is_visible = models.BooleanField(
        default=True
    )

    is_editable = models.BooleanField(
        default=True
    )

    is_filterable = models.BooleanField(
        default=True
    )

    is_searchable = models.BooleanField(
        default=True
    )

    is_sortable = models.BooleanField(
        default=True
    )

    # =====================================================
    # FK DETAILS
    # =====================================================

    related_model = models.CharField(
        max_length=150,
        null=True,
        blank=True
    )

    related_app = models.CharField(
        max_length=150,
        null=True,
        blank=True
    )

    # =====================================================

    order_no = models.IntegerField(
        default=1
    )

    description = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:

        ordering = ["order_no"]

        verbose_name = "User Screen Column"

        verbose_name_plural = "User Screen Columns"

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "userscreen_id",
                    "column_name"
                ],
                condition=models.Q(is_deleted=False),
                name="uq_userscreen_column"
            )
        ]

    def __str__(self):

        return f"{self.userscreen_id} - {self.column_name}"

    def delete(self, *args, **kwargs):

        self.is_active = False

        self.is_deleted = True

        self.save(
            update_fields=[
                "is_active",
                "is_deleted"
            ]
        )