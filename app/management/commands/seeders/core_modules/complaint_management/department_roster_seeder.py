"""Customer Care department + its 1-supervisor/5-member roster.

Every complaint category routes to a single "Customer Care" department, and
tickets are handed out to whichever active member currently holds the fewest
open tickets (see
`app.services.complaint_ticket_routing._pick_least_loaded_staff`).

Must run AFTER the staff/role-assigns seed groups (needs a UserType to
attach staff logins to) and `complaint_ticket_category` (backfills
`default_department` on existing categories), and BEFORE `routing_rule`
(which routes by `default_department`).
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_management import ComplaintCategory, ComplaintDepartmentMember
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.role_assigns.userType import UserType
from app.models.staff_creations.department import Department
from app.models.staff_creations.staffcreation import Staffcreation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class ComplaintDepartmentRosterSeeder(BaseSeeder):
    name = "complaint_department_roster"

    PASSWORD = "CustomerCare123"
    DEPARTMENT_CODE = "CUSTOMER_CARE"
    DEPARTMENT_NAME = "Customer Care"
    SUPERVISOR_ROLE_NAME = "Customer Care Supervisor"
    MEMBER_ROLE_NAME = "Customer Care Executive"

    SUPERVISOR = ("cc_supervisor", "Anitha Raj", "Customer Care Supervisor")

    # (username, employee_name, designation)
    MEMBERS = [
        ("cc_exec_1", "Ramesh Nair", "Customer Care Executive"),
        ("cc_exec_2", "Priya Thomas", "Customer Care Executive"),
        ("cc_exec_3", "Anil Kumar", "Customer Care Executive"),
        ("cc_exec_4", "Sneha Pillai", "Customer Care Executive"),
        ("cc_exec_5", "Devika Menon", "Customer Care Executive"),
    ]

    def _resolve_tenancy(self):
        companies = list(Company.objects.filter(is_deleted=False, is_active=True)[:2])
        if len(companies) != 1:
            return None, None
        company = companies[0]
        projects = list(
            Project.objects.filter(
                company_id=company, is_deleted=False, is_active=True
            ).order_by("unique_id")[:2]
        )
        return company, (projects[0] if len(projects) == 1 else None)

    def _upsert_staff(self, *, username, name, designation, role, staff_type, company, project):
        staff, created = Staffcreation.objects.get_or_create(
            username=username,
            defaults={
                "employee_name": name,
                "designation": designation,
                "password": self.PASSWORD,
                "user_type_id": staff_type,
                "staffusertype_id": role,
                "company_id": company,
                "project_id": project,
                "is_active": True,
                "is_deleted": False,
                "is_superuser": False,
                "login_enabled": True,
                "approval_status": Staffcreation.APPROVAL_APPROVED,
            },
        )
        if not created:
            staff.employee_name = name
            staff.designation = designation
            staff.staffusertype_id = role
            staff.login_enabled = True
            staff.is_active = True
            staff.is_deleted = False
            staff.approval_status = Staffcreation.APPROVAL_APPROVED
            if (
                staff.company_id_id != getattr(company, "pk", None)
                or staff.project_id_id != getattr(project, "pk", None)
            ):
                staff.staff_id = None
            staff.company_id = company
            staff.project_id = project
            staff.save()
        return staff, created

    def run(self):
        staff_type = UserType.objects.filter(name__iexact="staff").first()
        if not staff_type:
            self.log("UserType 'staff' missing — run the role-assigns seed group first. Skipping.")
            return

        company, project = self._resolve_tenancy()
        if not company:
            self.log("Could not resolve a single active company — skipping department roster.")
            return

        department, _ = Department.objects.get_or_create(
            department_code=self.DEPARTMENT_CODE,
            company_id=company,
            project_id=project,
            defaults={
                "department_name": self.DEPARTMENT_NAME,
                "is_active": True,
                "is_deleted": False,
            },
        )

        supervisor_role, _ = StaffUserType.objects.get_or_create(
            name=self.SUPERVISOR_ROLE_NAME,
            usertype_id=staff_type,
            defaults={"is_active": True, "is_deleted": False},
        )
        member_role, _ = StaffUserType.objects.get_or_create(
            name=self.MEMBER_ROLE_NAME,
            usertype_id=staff_type,
            defaults={"is_active": True, "is_deleted": False},
        )

        username, name, designation = self.SUPERVISOR
        supervisor, supervisor_created = self._upsert_staff(
            username=username, name=name, designation=designation,
            role=supervisor_role, staff_type=staff_type, company=company, project=project,
        )
        ComplaintDepartmentMember.objects.update_or_create(
            department=department,
            staff=supervisor,
            defaults={
                "is_supervisor": True,
                "is_active": True,
                "is_deleted": False,
                "company_id": company,
                "project_id": project,
            },
        )

        member_created_count = 0
        for username, name, designation in self.MEMBERS:
            member, created = self._upsert_staff(
                username=username, name=name, designation=designation,
                role=member_role, staff_type=staff_type, company=company, project=project,
            )
            member_created_count += 1 if created else 0
            ComplaintDepartmentMember.objects.update_or_create(
                department=department,
                staff=member,
                defaults={
                    "is_supervisor": False,
                    "is_active": True,
                    "is_deleted": False,
                    "company_id": company,
                    "project_id": project,
                },
            )

        # Every complaint category routes here — this deployment has one
        # customer-care desk handling all complaint types, not one team per
        # category. Never overwrites a category that already has an operator-
        # chosen default_department.
        updated_categories = ComplaintCategory.objects.filter(
            default_department__isnull=True, is_deleted=False,
        ).update(default_department=department)

        self.log(
            f"---Customer Care roster seeded (1 supervisor +{member_created_count} new of "
            f"{len(self.MEMBERS)} member logins, password {self.PASSWORD}); "
            f"{updated_categories} categor(y/ies) defaulted to Customer Care---"
        )
