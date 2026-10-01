import inspect

import app.utils.screen_dependencies as deps


def test_daily_trip_plan_groups_its_three_screens():
    assert deps.screen_group("daily-trip-assignments") == ("daily-trip-plan", "Daily Trip Plan")
    assert deps.screen_group("daily-trip-collection-points")[0] == "daily-trip-plan"
    assert deps.screen_group("daily-trip-household-collections")[0] == "daily-trip-plan"
    assert deps.screen_group("trip-plans") == (None, None)


def test_staff_user_type_groups_staff_and_contractor_types():
    assert deps.screen_group("staffusertypes") == ("staff-user-type", "Staff User Type")
    assert deps.screen_group("contractorusertypes")[0] == "staff-user-type"


def test_grouped_screens_are_real_catalog_screens():
    from app.utils.permission_catalog import SCREEN_LABELS

    for group in deps.SCREEN_GROUPS.values():
        assert group["screens"], group
        for name in group["screens"]:
            assert name in SCREEN_LABELS, name


def test_a_screen_belongs_to_at_most_one_group():
    names = [n for g in deps.SCREEN_GROUPS.values() for n in g["screens"]]
    assert len(names) == len(set(names))


def test_complaint_pages_group_their_backing_screens():
    for name in ("types", "categories", "subcategories", "sla-rules"):
        assert deps.screen_group(name) == ("complaint-types", "Complaint Types")
    for name in ("tickets", "reopen-history", "address-change", "notifications"):
        assert deps.screen_group(name) == ("complaint-desk", "Complaint Desk")
