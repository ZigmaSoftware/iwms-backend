from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth import get_user_model

from api.apps.company import Company
from api.apps.project import Project


User = get_user_model()


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    # This keeps Django admin usable for platform super admins without exposing business shortcuts.
    list_display = ("id", "username", "unique_id", "is_superuser", "company_id", "is_active")
    list_filter = ("is_superuser", "is_active", "is_deleted", "is_staff")
    search_fields = ("username", "unique_id")
    ordering = ("-id",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Platform", {"fields": ("is_superuser", "is_staff", "is_active")}),
        ("Tenant Links", {"fields": ("company_id", "project_id", "user_type_id", "staffusertype_id", "staff_id", "customer_id")}),
        ("Flags", {"fields": ("is_deleted",)}),
        ("Dates", {"fields": ("last_login", "created_at", "updated_at")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
    )

    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "password1", "password2", "is_superuser", "is_staff", "is_active")}),
    )


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("unique_id", "name", "is_active", "is_deleted")
    search_fields = ("unique_id", "name")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("unique_id", "name", "company_id", "is_active", "is_deleted")
    search_fields = ("unique_id", "name", "company_id__name")
