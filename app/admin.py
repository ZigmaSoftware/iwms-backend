from django.contrib import admin

from app.models.superadminmasters.company import Company
from app.models.superadminmasters.project import Project
from app.models.users.staffcreation import StaffOfficeDetails, StaffPersonalDetails
from app.models.customers.customercreation import CustomerCreation


@admin.register(StaffOfficeDetails)
class StaffOfficeDetailsAdmin(admin.ModelAdmin):
    list_display = ("id", "employee_name", "username", "email", "is_active", "is_deleted")
    list_filter = ("is_active", "is_deleted", "is_staff")
    search_fields = ("employee_name", "username", "email", "staff_unique_id")
    ordering = ("-id",)


@admin.register(StaffPersonalDetails)
class StaffPersonalDetailsAdmin(admin.ModelAdmin):
    list_display = ("id", "staff", "contact_mobile", "contact_email")
    search_fields = ("staff__employee_name", "contact_mobile")
    ordering = ("-id",)


@admin.register(CustomerCreation)
class CustomerCreationAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_name", "contact_no", "username", "is_active", "is_deleted")
    list_filter = ("is_active", "is_deleted")
    search_fields = ("customer_name", "contact_no", "username")
    ordering = ("-id",)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("unique_id", "name", "is_active", "is_deleted")
    search_fields = ("unique_id", "name")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("unique_id", "name", "company_id", "is_active", "is_deleted")
    search_fields = ("unique_id", "name", "company_id__name")
