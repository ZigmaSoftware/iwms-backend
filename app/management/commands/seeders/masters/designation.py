from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.department import Department
from app.models.masters.designation import Designation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class DesignationSeeder(BaseSeeder):
    name = "designation"

    # (designation_name, department_code)
    designations = [
        # Management
        ("General Manager",          "MGMT"),
        ("Deputy General Manager",   "MGMT"),
        ("Assistant General Manager","MGMT"),

        # Human Resources
        ("HR Manager",               "HR"),
        ("HR Executive",             "HR"),
        ("Recruitment Officer",      "HR"),
        ("Payroll Officer",          "HR"),

        # Administration
        ("Admin Manager",            "ADMIN"),
        ("Admin Executive",          "ADMIN"),
        ("Office Assistant",         "ADMIN"),

        # Finance
        ("Finance Manager",          "FIN"),
        ("Finance Executive",        "FIN"),
        ("Financial Analyst",        "FIN"),

        # Accounts
        ("Accounts Manager",         "ACC"),
        ("Senior Accountant",        "ACC"),
        ("Junior Accountant",        "ACC"),
        ("Billing Officer",          "ACC"),

        # Information Technology
        ("IT Manager",               "IT"),
        ("Software Engineer",        "IT"),
        ("System Administrator",     "IT"),
        ("IT Support",               "IT"),

        # Operations
        ("Operations Manager",       "OPS"),
        ("Operations Supervisor",    "OPS"),
        ("Senior Operator",          "OPS"),
        ("Operator",                 "OPS"),
        ("Helper",                   "OPS"),

        # Transport
        ("Transport Manager",        "TRANS"),
        ("Fleet Supervisor",         "TRANS"),
        ("Senior Driver",            "TRANS"),
        ("Driver",                   "TRANS"),

        # Field Operations
        ("Field Manager",            "FIELD"),
        ("Field Supervisor",         "FIELD"),
        ("Field Operator",           "FIELD"),
        ("Sanitation Worker",        "FIELD"),

        # Customer Service
        ("Customer Service Manager", "CS"),
        ("Customer Service Executive","CS"),

        # Health & Safety
        ("Safety Manager",           "HS"),
        ("Safety Officer",           "HS"),
        ("Health & Safety Inspector","HS"),

        # Procurement
        ("Procurement Manager",      "PROC"),
        ("Procurement Officer",      "PROC"),
    ]

    def run(self):
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project")

        dept_cache: dict[str, Department] = {}

        for designation_name, dept_code in self.designations:
            if dept_code not in dept_cache:
                dept = Department.objects.filter(
                    company_id=company,
                    project_id=project,
                    department_code=dept_code,
                    is_deleted=False,
                ).first()
                if not dept:
                    self.log_error(f"Department '{dept_code}' not found — skipping {designation_name}")
                    continue
                dept_cache[dept_code] = dept

            department = dept_cache[dept_code]

            designation, created = Designation.objects.update_or_create(
                company_id=company,
                project_id=project,
                designation_name=designation_name,
                department_id=department,
                defaults={
                    "description": f"{designation_name} — {department.department_name}",
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            action = "Created" if created else "Updated"
            self.log(f"{designation.designation_name} [{dept_code}] ({action})")
