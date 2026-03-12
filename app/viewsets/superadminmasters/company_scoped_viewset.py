# from django.db.models import Q
# from rest_framework import viewsets
# from rest_framework.exceptions import PermissionDenied, ValidationError

# from django.contrib.auth.models import User
# from app.models.user_creations.staffcreation import Staffcreation
# from app.models.superadmin_masters.company import Company
# from app.models.superadmin_masters.project import Project
# from app.utils.base_models import Account


# class CompanyScopedViewSet(viewsets.ModelViewSet):
#     """
#     Enterprise Multi-Tenant Base ViewSet

#     🔵 Platform Superadmin
#         - Full access
#         - company_id & project_id optional

#     🟢 Company Users (Admin/Staff)
#         - Scoped to their company
#         - project_id required
#         - company_id auto assigned
#     """

#     project_header = "X-Project-Id"

#     # ==========================================================
#     # ACCOUNT RESOLUTION
#     # ==========================================================

#     from django.db.models import Q

#     def _get_account(self):
#         user = self.request.user

#         if not user or not user.is_authenticated:
#             return None

#         # If Django User
#         from app.models.superadmin_masters.auth_user import User as AuthUser
#         from app.models.user_creations.staffcreation import Staffcreation

#         if isinstance(user, AuthUser):
#             account, _ = Account.objects.get_or_create(user=user)
#             return account

#         # If Staffcreation
#         if isinstance(user, Staffcreation):
#             account, _ = Account.objects.get_or_create(staff=user)
#             return account

#         return None

#     # ==========================================================
#     # SUPER ADMIN CHECK
#     # ==========================================================

#     def _is_platform_super_admin(self):
#         user = getattr(self.request, "user", None)

#         return bool(
#             user
#             and user.is_authenticated
#             and getattr(user, "is_superuser", False)
#             and getattr(user, "company_id", None) is None
#         )

#     # ==========================================================
#     # COMPANY RESOLUTION
#     # ==========================================================

#     def _company(self):
#         user = getattr(self.request, "user", None)
#         if not user:
#             return None

#         return getattr(user, "company_id", None)

#     # ==========================================================
#     # PROJECT RESOLUTION
#     # ==========================================================

#     def _project(self):
#         company = self._company()
#         if not company:
#             return None

#         project_unique_id = (
#             self.request.headers.get(self.project_header)
#             or self.request.query_params.get("project")
#             or self.request.data.get("project_id")
#             or self.request.data.get("project_unique_id")
#         )

#         if not project_unique_id:
#             return None

#         project = Project.objects.filter(
#             unique_id=project_unique_id,
#             company_id=company
#         ).first()

#         if not project:
#             raise ValidationError({"project_id": "Invalid project_id for this company"})

#         return project

#     # ==========================================================
#     # QUERYSET FILTERING
#     # ==========================================================

#     def filter_queryset(self, queryset):
#         queryset = super().filter_queryset(queryset)

#         # 🔵 Superadmin sees everything
#         if self._is_platform_super_admin():
#             return queryset

#         # 🟢 Company users
#         company = self._company()
#         if not company:
#             raise PermissionDenied("Company user required")

#         if hasattr(queryset.model, "company_id"):
#             queryset = queryset.filter(company_id=company)

#         project = self._project()
#         if project and hasattr(queryset.model, "project_id"):
#             queryset = queryset.filter(project_id=project)

#         return queryset

#     # ==========================================================
#     # CREATE
#     # ==========================================================

#     def perform_create(self, serializer):
#         model = getattr(getattr(serializer, "Meta", None), "model", None)
#         account = self._get_account()

#         # 🔵 Platform Superadmin
#         if self._is_platform_super_admin():
#             save_kwargs = {}

#             if model and hasattr(model, "company_id"):
#                 save_kwargs["company_id"] = None

#             if model and hasattr(model, "project_id"):
#                 save_kwargs["project_id"] = None

#             serializer.save(**save_kwargs, created_by=account)
#             return

#         # 🟢 Company User
#         company = self._company()
#         if not company:
#             raise PermissionDenied("Company user required")

#         save_kwargs = {}

#         if model and hasattr(model, "company_id"):
#             save_kwargs["company_id"] = company

#         if model and hasattr(model, "project_id"):
#             project = self._project()
#             if not project:
#                 raise ValidationError({"project_id": "project_id is required"})
#             save_kwargs["project_id"] = project

#         serializer.save(**save_kwargs, created_by=account)

#     # ==========================================================
#     # UPDATE
#     # ==========================================================

#     def perform_update(self, serializer):
#         account = self._get_account()

#         # 🔵 Superadmin
#         if self._is_platform_super_admin():
#             serializer.save(updated_by=account)
#             return

#         # 🟢 Company User
#         company = self._company()
#         if not company:
#             raise PermissionDenied("Company user required")

#         instance = serializer.instance
#         model = getattr(getattr(serializer, "Meta", None), "model", None)

#         save_kwargs = {}

#         if model and hasattr(model, "company_id"):
#             save_kwargs["company_id"] = getattr(instance, "company_id", None) or company

#         if model and hasattr(model, "project_id"):
#             save_kwargs["project_id"] = getattr(instance, "project_id", None) or self._project()

#         serializer.save(**save_kwargs, updated_by=account)

#     # ==========================================================
#     # DELETE (Soft delete compatible)
#     # ==========================================================

#     def perform_destroy(self, instance):
#         account = self._get_account()

#         if hasattr(instance, "is_deleted"):
#             instance.is_deleted = True
#             if hasattr(instance, "updated_by"):
#                 instance.updated_by = account
#             instance.save()
#         else:
#             instance.delete()


from django.db.models import Q
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError

from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.user_creations.staffcreation import Staffcreation
from app.utils.base_models import Account


class CompanyScopedViewSet(viewsets.ModelViewSet):
    """
    Enterprise Multi-Tenant Base ViewSet

    PLATFORM SUPERADMIN
        • Full access
        • Must send company_id when creating company-scoped models

    COMPANY USERS
        • Scoped to their company
        • company_id automatically assigned
        • project_id required
    """

    project_header = "X-Project-Id"

    # ==========================================================
    # ACCOUNT RESOLUTION
    # ==========================================================

    def _get_account(self):
        user = self.request.user

        if not user or not user.is_authenticated:
            return None

        if isinstance(user, Staffcreation):
            account, _ = Account.objects.get_or_create(staff=user)
            return account

        account, _ = Account.objects.get_or_create(user=user)
        return account

    # ==========================================================
    # SUPERADMIN CHECK
    # ==========================================================

    def _is_platform_super_admin(self):
        user = getattr(self.request, "user", None)

        return bool(
            user
            and user.is_authenticated
            and getattr(user, "is_superuser", False)
            and getattr(user, "company_id", None) is None
        )

    # ==========================================================
    # COMPANY RESOLUTION
    # ==========================================================

    def _company(self):
        user = getattr(self.request, "user", None)

        if not user:
            return None

        return getattr(user, "company_id", None)

    # ==========================================================
    # PROJECT RESOLUTION
    # ==========================================================

    def _project(self):

        company = self._company()

        if not company:
            return None

        project_unique_id = (
            self.request.headers.get(self.project_header)
            or self.request.query_params.get("project")
            or self.request.data.get("project_id")
            or self.request.data.get("project_unique_id")
        )

        if not project_unique_id:
            return None

        project = Project.objects.filter(
            unique_id=project_unique_id,
            company_id=company
        ).first()

        if not project:
            raise ValidationError({"project_id": "Invalid project_id for this company"})

        return project

    # ==========================================================
    # QUERYSET FILTERING
    # ==========================================================

    def filter_queryset(self, queryset):

        queryset = super().filter_queryset(queryset)

        # PLATFORM SUPERADMIN
        if self._is_platform_super_admin():
            return queryset

        # COMPANY USERS
        company = self._company()

        if not company:
            raise PermissionDenied("Company user required")

        if hasattr(queryset.model, "company_id"):
            queryset = queryset.filter(company_id=company)

        project = self._project()

        if project and hasattr(queryset.model, "project_id"):
            queryset = queryset.filter(project_id=project)

        return queryset

    # ==========================================================
    # CREATE
    # ==========================================================

    def perform_create(self, serializer):

        model = getattr(getattr(serializer, "Meta", None), "model", None)
        account = self._get_account()

        # ------------------------------------------------------
        # PLATFORM SUPERADMIN
        # ------------------------------------------------------

        if self._is_platform_super_admin():

            save_kwargs = {}

            if model and hasattr(model, "company_id"):

                company_unique_id = self.request.data.get("company_id")

                if not company_unique_id:
                    raise ValidationError({"company_id": "company_id is required"})

                company = Company.objects.filter(
                    unique_id=company_unique_id
                ).first()

                if not company:
                    raise ValidationError({"company_id": "Invalid company_id"})

                save_kwargs["company_id"] = company

            if model and hasattr(model, "project_id"):

                project_unique_id = (
                    self.request.headers.get(self.project_header)
                    or self.request.data.get("project_id")
                )

                if project_unique_id:

                    project = Project.objects.filter(
                        unique_id=project_unique_id
                    ).first()

                    if not project:
                        raise ValidationError({"project_id": "Invalid project_id"})

                    save_kwargs["project_id"] = project

            serializer.save(**save_kwargs, created_by=account)
            return

        # ------------------------------------------------------
        # COMPANY USER
        # ------------------------------------------------------

        company = self._company()

        if not company:
            raise PermissionDenied("Company user required")

        save_kwargs = {}

        if model and hasattr(model, "company_id"):
            save_kwargs["company_id"] = company

        if model and hasattr(model, "project_id"):

            project = self._project()

            if not project:
                raise ValidationError({"project_id": "project_id is required"})

            save_kwargs["project_id"] = project

        serializer.save(**save_kwargs, created_by=account)

    # ==========================================================
    # UPDATE
    # ==========================================================

    def perform_update(self, serializer):

        account = self._get_account()

        if self._is_platform_super_admin():
            serializer.save(updated_by=account)
            return

        company = self._company()

        if not company:
            raise PermissionDenied("Company user required")

        instance = serializer.instance
        model = getattr(getattr(serializer, "Meta", None), "model", None)

        save_kwargs = {}

        if model and hasattr(model, "company_id"):
            save_kwargs["company_id"] = getattr(instance, "company_id", None) or company

        if model and hasattr(model, "project_id"):
            save_kwargs["project_id"] = getattr(instance, "project_id", None) or self._project()

        serializer.save(**save_kwargs, updated_by=account)

    # ==========================================================
    # DELETE (SOFT DELETE SUPPORT)
    # ==========================================================

    def perform_destroy(self, instance):

        account = self._get_account()

        if hasattr(instance, "is_deleted"):

            instance.is_deleted = True

            if hasattr(instance, "updated_by"):
                instance.updated_by = account

            instance.save()

        else:
            instance.delete()