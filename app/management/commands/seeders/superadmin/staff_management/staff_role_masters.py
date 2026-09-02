"""Departments and designations for the operational staff roles.

The legacy DepartmentSeeder/DesignationSeeder (removed — they bootstrapped a
generic "IWMS" company and were never registered) are replaced by this
seeder, which covers just the roles the field workforce is built from —
operator/collector, driver and supervisor — against the company that is
actually present, so it composes with BluePlanetSeeder.

Department codes and designation names match the lookups in
staff_office.py (_get_dept / _get_desg), so StaffcreationSeeder resolves
against these rows.
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.staff_creations.department import Department
from app.models.staff_creations.designation import Designation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class StaffRoleMastersSeeder(BaseSeeder):
    name = "staff-role-masters"

    # (code, name, description)
    DEPARTMENTS = [
        ("OPS",   "Operations", "Waste collection and day-to-day operations"),
        ("TRANS", "Transport",  "Fleet and vehicle management"),
    ]

    # (designation_name, department_code, group, description)
    # "Operator" and "Driver" are the names staff_office.py looks up; the
    # collector role is the same field job under its operational name, so it
    # is seeded alongside rather than renaming the one staff seeding needs.
    DESIGNATIONS = [
        ("Operator",              "OPS",   "field",      "Vehicle operator / waste collection crew"),
        ("Collector",             "OPS",   "field",      "Door-to-door waste collector"),
        ("Driver",                "TRANS", "field",      "Collection vehicle driver"),
        ("Operations Supervisor", "OPS",   "supervisor", "Supervises collection crews and daily trips"),
    ]

    def _resolve_tenant(self):
        """Use the existing company/project rather than bootstrapping one."""
        company = Company.objects.filter(is_deleted=False).order_by("name").first()
        if not company:
            self.log_error("No company found — run the company seeder first.")
            return None, None

        project = Project.objects.filter(
            company_id=company, is_deleted=False
        ).order_by("name").first()
        if not project:
            self.log_error(
                f"No project found for company '{company.name}' — "
                "run the project seeder first."
            )
            return None, None

        return company, project

    def run(self):
        company, project = self._resolve_tenant()
        if not company or not project:
            return

        self.log(f"Seeding for company '{company.name}' / project '{project.name}'")

        departments: dict[str, Department] = {}
        for code, name, description in self.DEPARTMENTS:
            department, created = Department.objects.update_or_create(
                company_id=company,
                project_id=project,
                department_code=code,
                defaults={
                    "department_name": name,
                    "description": description,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            departments[code] = department
            self.log(f"Department {code} — {name} ({'Created' if created else 'Updated'})")

        for designation_name, dept_code, group, description in self.DESIGNATIONS:
            department = departments.get(dept_code)
            if not department:
                self.log_error(
                    f"Department '{dept_code}' missing — skipping {designation_name}"
                )
                continue

            designation, created = Designation.objects.update_or_create(
                company_id=company,
                project_id=project,
                designation_name=designation_name,
                department_id=department,
                defaults={
                    "designation_group": group,
                    "description": description,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            self.log(
                f"Designation {designation.designation_name} [{dept_code}] "
                f"({'Created' if created else 'Updated'})"
            )

        self.log(
            f"---Staff role masters seeded "
            f"({len(self.DEPARTMENTS)} departments, {len(self.DESIGNATIONS)} designations)---"
        )
