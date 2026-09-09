"""A staff member belongs to exactly one mobile app.

The app used to live in two places — `StaffcreationOfficeDetails.app_module`
and a `StaffAccessConfiguration.app_modules` many-to-many — which could
disagree and strand someone in an app they had no screens for. It is now a
single FK on the access configuration, with the staff record reading back
through it. These cover the resolution rules that enforce that.
"""

import pytest
from rest_framework import serializers

from app.models.screen_managements.app_module import AppModule
from app.serializers.superadmin.staff_management.staff_access_configuration_serializer import (
    StaffAccessConfigurationSerializer,
)


@pytest.fixture
def modules(db):
    return [
        AppModule.objects.create(
            module_key=f"app-{k}", surface_key=k, label=k.title(), route=f"/{k}/home", order_no=i
        )
        for i, k in enumerate(("driver", "supervisor"), start=1)
    ]


def _resolve(payload):
    s = StaffAccessConfigurationSerializer()
    s.initial_data = payload
    return s._resolve_app_module(payload)


def test_single_id_resolves(modules):
    assert _resolve({"app_module_id": modules[0].unique_id}) == modules[0]


def test_legacy_single_element_list_resolves(modules):
    assert _resolve({"app_module_ids": [modules[1].unique_id]}) == modules[1]


def test_legacy_multi_element_list_is_rejected(modules):
    with pytest.raises(serializers.ValidationError) as exc:
        _resolve({"app_module_ids": [m.unique_id for m in modules]})
    assert "only one mobile app" in str(exc.value)


def test_blank_means_no_app(modules):
    assert _resolve({"app_module_id": ""}) is None
    assert _resolve({"app_module_ids": []}) is None


def test_unknown_id_is_rejected(modules):
    with pytest.raises(serializers.ValidationError):
        _resolve({"app_module_id": "APPMOD-nope"})


def test_field_sent_detection():
    s = StaffAccessConfigurationSerializer()
    s.initial_data = {"description": "x"}
    assert s._app_module_field_sent() is False
    s.initial_data = {"app_module_id": None}
    assert s._app_module_field_sent() is True
    s.initial_data = {"app_module_ids": []}
    assert s._app_module_field_sent() is True


def test_staff_app_module_reads_through_access_configuration(db, modules):
    """`Staffcreation.app_module` reflects the access configuration, and only it."""
    from app.models.staff_creations.staff_access_configuration import (
        StaffAccessConfiguration,
    )
    from app.models.staff_creations.staffcreation import Staffcreation
    from app.models.superadmin_masters.company import Company

    company = Company.objects.create(name="Acme")
    staff = Staffcreation.objects.create(employee_name="Ravi", company_id=company)

    # No configuration at all — no mobile access.
    assert staff.app_module is None

    config = StaffAccessConfiguration.objects.create(
        staff_id=staff, company_id=company, app_module=modules[0],
    )
    assert Staffcreation.objects.get(pk=staff.pk).app_module == modules[0].surface_key

    # Clearing the selection revokes mobile access rather than leaving a
    # stale surface key behind on the staff record.
    config.app_module = None
    config.save(update_fields=["app_module"])
    assert Staffcreation.objects.get(pk=staff.pk).app_module is None
