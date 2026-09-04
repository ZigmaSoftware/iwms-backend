from django.db.models import Q
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError

from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.staff_creations.staffcreation import Staffcreation
from app.utils.base_models import Account


class CompanyScopedViewSet(viewsets.ModelViewSet):

    project_header = "X-Project-Id"

    # ==========================================================
    # HELPER — only pass created_by/updated_by if model supports it
    # ==========================================================

    def _build_save_kwargs(self, serializer, base_kwargs: dict, **audit_fields) -> dict:
        """
        Merges base_kwargs with audit fields (created_by, updated_by)
        only if the model actually has those fields.
        Prevents TypeError for models that don't extend BaseMaster.
        """
        model = getattr(getattr(serializer, "Meta", None), "model", None)
        result = dict(base_kwargs)

        for field_name, value in audit_fields.items():
            if model and hasattr(model, field_name):
                result[field_name] = value

        return result

    def _first_present_data_value(self, *keys):
        """
        Returns (is_present, value) for the first key found in request.data.
        Distinguishes between omitted keys and explicit null values.
        """
        data = getattr(self.request, "data", {}) or {}
        for key in keys:
            if key in data:
                return True, data.get(key)
        return False, None

    @staticmethod
    def _is_nullish(value):
        if value is None:
            return True
        if isinstance(value, str) and value.strip().lower() in {"", "null", "none"}:
            return True
        return False

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
            or self.request.query_params.get("project_id")
            or self.request.query_params.get("project_unique_id")
            or self.request.query_params.get("project")
            or self.request.data.get("project_id_input")
            or self.request.data.get("project_id")
            or self.request.data.get("project_unique_id")
        )

        if not project_unique_id:
            # Mobile apps (driver/operator/supervisor) never send a project
            # header or field — they only ever operate within their own
            # single project. Desktop/admin callers that manage several
            # projects under one company are expected to keep sending one
            # explicitly; this fallback only fires when nothing was given
            # at all, so it never silently overrides an explicit choice.
            user = getattr(self.request, "user", None)
            own_project_id = getattr(user, "project_id_id", None)
            if own_project_id:
                project_unique_id = own_project_id
            else:
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

        if self._is_platform_super_admin():
            # Apply optional company/project filters from query params for superadmin list views
            company_id_param = (
                self.request.query_params.get("company_id")
                or self.request.query_params.get("company_unique_id")
            )
            project_id_param = (
                self.request.query_params.get("project_id")
                or self.request.query_params.get("project_unique_id")
                or self.request.query_params.get("project")
            )
            if company_id_param and hasattr(queryset.model, "company_id"):
                queryset = queryset.filter(company_id=company_id_param)
            if project_id_param and hasattr(queryset.model, "project_id"):
                # "none" is the sentinel used by the frontend for company-wide
                # (no-project) records, since a URL/query value can't be empty.
                if project_id_param == "none":
                    queryset = queryset.filter(project_id__isnull=True)
                else:
                    queryset = queryset.filter(project_id=project_id_param)
            return queryset

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

        # PLATFORM SUPERADMIN
        if self._is_platform_super_admin():

            save_kwargs = {}

            if model and hasattr(model, "company_id"):
                company_field = model._meta.get_field("company_id")
                has_company_input, company_input = self._first_present_data_value(
                    "company_id_input",
                    "company_id",
                )

                if has_company_input:
                    if self._is_nullish(company_input):
                        if not company_field.null:
                            raise ValidationError({"company_id": "company_id cannot be null"})
                        save_kwargs["company_id"] = None
                    else:
                        company = Company.objects.filter(unique_id=company_input).first()
                        if not company:
                            raise ValidationError({"company_id": "Invalid company_id"})
                        save_kwargs["company_id"] = company
                elif not company_field.null:
                    raise ValidationError({"company_id": "company_id is required"})

            if model and hasattr(model, "project_id"):
                project_field = model._meta.get_field("project_id")
                header_project = self.request.headers.get(self.project_header)
                has_project_input, project_input = self._first_present_data_value(
                    "project_id_input",
                    "project_id",
                )

                project_provided = False
                project_unique_id = None

                if not self._is_nullish(header_project):
                    project_provided = True
                    project_unique_id = header_project
                elif has_project_input:
                    project_provided = True
                    if not self._is_nullish(project_input):
                        project_unique_id = project_input

                if project_provided and project_unique_id is None:
                    if not project_field.null:
                        raise ValidationError({"project_id": "project_id cannot be null"})
                    save_kwargs["project_id"] = None
                elif project_unique_id is not None:
                    project = Project.objects.filter(unique_id=project_unique_id).first()
                    if not project:
                        raise ValidationError({"project_id": "Invalid project_id"})
                    save_kwargs["project_id"] = project

            # ← safe: only pass created_by if model has the field
            final_kwargs = self._build_save_kwargs(
                serializer, save_kwargs, created_by=account
            )
            serializer.save(**final_kwargs)
            return

        # COMPANY USER
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

        # ← safe: only pass created_by if model has the field
        final_kwargs = self._build_save_kwargs(
            serializer, save_kwargs, created_by=account
        )
        serializer.save(**final_kwargs)

    # ==========================================================
    # UPDATE
    # ==========================================================

    def perform_update(self, serializer):

        account = self._get_account()

        # PLATFORM SUPERADMIN
        if self._is_platform_super_admin():

            save_kwargs = {}
            model = getattr(getattr(serializer, "Meta", None), "model", None)
            instance = serializer.instance

            if model and hasattr(model, "company_id"):
                company_field = model._meta.get_field("company_id")
                has_company_input, company_input = self._first_present_data_value(
                    "company_id_input",
                    "company_id",
                )

                if has_company_input:
                    if self._is_nullish(company_input):
                        if not company_field.null:
                            raise ValidationError({"company_id": "company_id cannot be null"})
                        save_kwargs["company_id"] = None
                    else:
                        company = Company.objects.filter(unique_id=company_input).first()
                        if not company:
                            raise ValidationError({"company_id": "Invalid company_id"})
                        save_kwargs["company_id"] = company
                else:
                    save_kwargs["company_id"] = getattr(instance, "company_id", None)

            if model and hasattr(model, "project_id"):
                project_field = model._meta.get_field("project_id")
                header_project = self.request.headers.get(self.project_header)
                has_project_input, project_input = self._first_present_data_value(
                    "project_id_input",
                    "project_id",
                )

                project_provided = False
                project_unique_id = None

                if not self._is_nullish(header_project):
                    project_provided = True
                    project_unique_id = header_project
                elif has_project_input:
                    project_provided = True
                    if not self._is_nullish(project_input):
                        project_unique_id = project_input

                if project_provided and project_unique_id is None:
                    if not project_field.null:
                        raise ValidationError({"project_id": "project_id cannot be null"})
                    save_kwargs["project_id"] = None
                elif project_unique_id is not None:
                    project = Project.objects.filter(unique_id=project_unique_id).first()
                    if not project:
                        raise ValidationError({"project_id": "Invalid project_id"})
                    save_kwargs["project_id"] = project
                else:
                    save_kwargs["project_id"] = getattr(instance, "project_id", None)

            # ← safe: only pass updated_by if model has the field
            final_kwargs = self._build_save_kwargs(
                serializer, save_kwargs, updated_by=account
            )
            serializer.save(**final_kwargs)
            return

        # COMPANY USER
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

        # ← safe: only pass updated_by if model has the field
        final_kwargs = self._build_save_kwargs(
            serializer, save_kwargs, updated_by=account
        )
        serializer.save(**final_kwargs)

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
