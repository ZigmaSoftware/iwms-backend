from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.department import Department
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class DepartmentSeeder(BaseSeeder):
    name = "department"

    departments = [
        ("Management", "MGMT", "Executive and senior management"),
        ("Human Resources", "HR", "Recruitment, payroll, employee welfare"),
        ("Administration", "ADMIN", "General administration and office management"),
        ("Finance", "FIN", "Financial planning and reporting"),
        ("Accounts", "ACC", "Day-to-day accounting and billing"),
        ("Information Technology", "IT", "Systems, software and IT infrastructure"),
        ("Operations", "OPS", "Waste collection and day-to-day operations"),
        ("Transport", "TRANS", "Fleet and vehicle management"),
        ("Field Operations", "FIELD", "On-ground sanitation and field work"),
        ("Customer Service", "CS", "Citizen grievances and customer support"),
        ("Health & Safety", "HS", "Occupational health and safety compliance"),
        ("Procurement", "PROC", "Purchasing and vendor management"),
    ]

    def run(self):
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project")

        for name, code, description in self.departments:
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
            action = "Created" if created else "Updated"
            self.log(f"Department {department.department_code} ({action})")
