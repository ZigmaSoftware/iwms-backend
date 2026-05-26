"""Unit tests for MainCategory, SubCategory grievance models."""
import pytest
from app.models.grivences.main_category_citizenGrievance import MainCategory
from app.models.grivences.sub_category_citizenGrievance import SubCategory


@pytest.mark.django_db
class TestMainCategoryModel:
    def test_create(self):
        mc = MainCategory.objects.create(main_categoryName="Road Issue")
        assert mc.main_categoryName == "Road Issue"
        assert mc.unique_id.startswith("CMPMC-")

    def test_str(self):
        mc = MainCategory.objects.create(main_categoryName="Water Issue")
        assert str(mc) == "Water Issue"

    def test_default_flags(self):
        mc = MainCategory.objects.create(main_categoryName="Sanitation")
        assert mc.is_active is True
        assert mc.is_deleted is False

    def test_soft_delete(self):
        mc = MainCategory.objects.create(main_categoryName="Waste")
        mc.delete()
        mc.refresh_from_db()
        assert mc.is_active is False
        assert mc.is_deleted is True

    def test_name_unique(self):
        from django.db import IntegrityError
        MainCategory.objects.create(main_categoryName="DupCategory")
        with pytest.raises(IntegrityError):
            MainCategory.objects.create(main_categoryName="DupCategory")


@pytest.mark.django_db
class TestSubCategoryModel:
    def test_create(self):
        mc = MainCategory.objects.create(main_categoryName="General")
        sc = SubCategory.objects.create(name="Missed Pickup", mainCategory=mc)
        assert sc.name == "Missed Pickup"
        assert sc.unique_id.startswith("CMPSC-")

    def test_str(self):
        mc = MainCategory.objects.create(main_categoryName="Collection")
        sc = SubCategory.objects.create(name="Late Collection", mainCategory=mc)
        assert "Late Collection" in str(sc)

    def test_default_flags(self):
        mc = MainCategory.objects.create(main_categoryName="Overflowing")
        sc = SubCategory.objects.create(name="Bin Full", mainCategory=mc)
        assert sc.is_active is True
        assert sc.is_deleted is False

    def test_soft_delete(self):
        mc = MainCategory.objects.create(main_categoryName="Broken")
        sc = SubCategory.objects.create(name="Broken Bin", mainCategory=mc)
        sc.delete()
        sc.refresh_from_db()
        assert sc.is_active is False
        assert sc.is_deleted is True

    def test_foreign_key_main_category(self):
        mc = MainCategory.objects.create(main_categoryName="Health")
        sc = SubCategory.objects.create(name="Spillage", mainCategory=mc)
        assert sc.mainCategory == mc
