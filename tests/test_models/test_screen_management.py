"""Unit tests for MainScreenType, MainScreen, UserScreen, UserScreenAction models."""
import pytest
from app.models.screen_managements.mainscreentype import MainScreenType
from app.models.screen_managements.mainscreen import MainScreen
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.userscreenaction import UserScreenAction


@pytest.mark.django_db
class TestMainScreenTypeModel:
    def test_create(self):
        mst = MainScreenType.objects.create(type_name="Masters")
        assert mst.type_name == "Masters"
        assert mst.unique_id.startswith("MSCRTYPE-")

    def test_str(self):
        mst = MainScreenType.objects.create(type_name="Reports")
        assert "Reports" in str(mst)

    def test_default_flags(self):
        mst = MainScreenType.objects.create(type_name="Dashboard")
        assert mst.is_active is True
        assert mst.is_deleted is False

    def test_soft_delete(self):
        mst = MainScreenType.objects.create(type_name="Admin")
        mst.delete()
        mst.refresh_from_db()
        assert mst.is_deleted is True


@pytest.mark.django_db
class TestMainScreenModel:
    def test_create(self):
        mst = MainScreenType.objects.create(type_name="Masters")
        ms = MainScreen.objects.create(
            mainscreen_name="common-masters",
            mainscreentype_id=mst,
            order_no=1,
        )
        assert ms.mainscreen_name == "common-masters"
        assert ms.unique_id.startswith("MAINSCREEN-")

    def test_str(self):
        mst = MainScreenType.objects.create(type_name="Admin")
        ms = MainScreen.objects.create(
            mainscreen_name="screen-managements",
            mainscreentype_id=mst,
            order_no=2,
        )
        assert "screen-managements" in str(ms)

    def test_default_flags(self):
        mst = MainScreenType.objects.create(type_name="Type2")
        ms = MainScreen.objects.create(
            mainscreen_name="test-screen",
            mainscreentype_id=mst,
            order_no=3,
        )
        assert ms.is_active is True
        assert ms.is_deleted is False

    def test_foreign_key_screentype(self):
        mst = MainScreenType.objects.create(type_name="Transport")
        ms = MainScreen.objects.create(
            mainscreen_name="transport",
            mainscreentype_id=mst,
            order_no=4,
        )
        assert ms.mainscreentype_id == mst


@pytest.mark.django_db
class TestUserScreenModel:
    def test_create(self):
        mst = MainScreenType.objects.create(type_name="Masters")
        ms = MainScreen.objects.create(
            mainscreen_name="masters",
            mainscreentype_id=mst,
            order_no=1,
        )
        us = UserScreen.objects.create(
            userscreen_name="states",
            mainscreen_id=ms,
            folder_name="masters",
            order_no=1,
        )
        assert us.userscreen_name == "states"
        assert us.unique_id.startswith("USERSCREEN-")

    def test_default_flags(self):
        mst = MainScreenType.objects.create(type_name="Admin")
        ms = MainScreen.objects.create(
            mainscreen_name="admin",
            mainscreentype_id=mst,
            order_no=2,
        )
        us = UserScreen.objects.create(
            userscreen_name="users",
            mainscreen_id=ms,
            folder_name="admin",
            order_no=1,
        )
        assert us.is_active is True
        assert us.is_deleted is False


@pytest.mark.django_db
class TestUserScreenActionModel:
    def test_create(self):
        action = UserScreenAction.objects.create(
            action_name="export",
            variable_name="can_export",
        )
        assert action.action_name == "export"
        assert action.unique_id.startswith("USERSCRNACT-")

    def test_str(self):
        action = UserScreenAction.objects.create(
            action_name="import",
            variable_name="can_import",
        )
        assert "import" in str(action)

    def test_default_flags(self):
        action = UserScreenAction.objects.create(
            action_name="print",
            variable_name="can_print",
        )
        assert action.is_active is True
        assert action.is_deleted is False
