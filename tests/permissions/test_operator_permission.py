from types import SimpleNamespace

import pytest

from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.permissions.operator_permission import IsOperatorRole


@pytest.mark.django_db
def test_operator_permission_resolves_staff_role_id_string(user_type):
    role = StaffUserType.objects.create(
        name="Company Driver",
        usertype_id=user_type.unique_id,
    )
    staff = Staffcreation.objects.create(
        employee_name="ASHISH KASANA",
        username="aashish",
        password="x",
        user_type_id=user_type.unique_id,
        staffusertype_id=role.unique_id,
        login_enabled=True,
        approval_status=Staffcreation.APPROVAL_APPROVED,
        is_deleted=False,
    )

    request = SimpleNamespace(user=staff)

    assert IsOperatorRole().has_permission(request, None) is True


@pytest.mark.django_db
def test_operator_permission_rejects_non_field_staff_role(user_type):
    role = StaffUserType.objects.create(
        name="Company Admin",
        usertype_id=user_type.unique_id,
    )
    staff = Staffcreation.objects.create(
        employee_name="Admin",
        username="admin-staff",
        password="x",
        user_type_id=user_type.unique_id,
        staffusertype_id=role.unique_id,
        login_enabled=True,
        approval_status=Staffcreation.APPROVAL_APPROVED,
        is_deleted=False,
    )

    request = SimpleNamespace(user=staff)

    assert IsOperatorRole().has_permission(request, None) is False
