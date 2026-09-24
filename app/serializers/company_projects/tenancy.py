from rest_framework import serializers


class TenancyReadSerializerMixin(serializers.Serializer):
    """Expose tenancy context consistently in responses.

    We keep these as read-only fields to avoid clients spoofing tenant ownership.

    `company_id`/`project_id` is a real ForeignKey on some models and a plain
    CharField holding the parent's `unique_id` on others (the codebase's
    string-pseudo-FK convention) — `getattr(obj, "company_id")` returns a
    `Company`/`Project` instance in the first case and a string in the
    second, so every accessor below branches on that instead of assuming
    one shape.
    """

    company_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    project_id = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()

    def get_company_id(self, obj):
        company = getattr(obj, "company_id", None)
        if isinstance(company, str) or company is None:
            return company
        return getattr(company, "unique_id", None)

    def get_company_name(self, obj):
        company = getattr(obj, "company_id", None)
        if isinstance(company, str):
            from app.models.superadmin_masters.company import Company
            company = Company.objects.filter(unique_id=company).first()
        return getattr(company, "name", None)

    def get_project_id(self, obj):
        project = getattr(obj, "project_id", None)
        if isinstance(project, str) or project is None:
            return project
        return getattr(project, "unique_id", None)

    def get_project_name(self, obj):
        project = getattr(obj, "project_id", None)
        if isinstance(project, str):
            from app.models.superadmin_masters.project import Project
            project = Project.objects.filter(unique_id=project).first()
        return getattr(project, "name", None)

