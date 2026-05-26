"""API tests for grievance (complaint categories, complaints) endpoints."""
import pytest
from app.models.grivences.main_category_citizenGrievance import MainCategory
from app.models.grivences.sub_category_citizenGrievance import SubCategory


@pytest.mark.django_db
class TestMainCategoryAPI:
    BASE = "/api/v1/grivences/main-category/"

    def test_list_unauthenticated(self, api_client):
        resp = api_client.get(self.BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated(self, auth_client):
        MainCategory.objects.create(main_categoryName="Road")
        resp = auth_client.get(self.BASE)
        assert resp.status_code == 200

    def test_create(self, auth_client):
        resp = auth_client.post(
            self.BASE, {"main_categoryName": "Electricity"}, format="json"
        )
        assert resp.status_code in (200, 201)

    def test_retrieve(self, auth_client):
        mc = MainCategory.objects.create(main_categoryName="Water Supply")
        resp = auth_client.get(f"{self.BASE}{mc.unique_id}/")
        assert resp.status_code == 200

    def test_update(self, auth_client):
        mc = MainCategory.objects.create(main_categoryName="Sewage")
        resp = auth_client.patch(
            f"{self.BASE}{mc.unique_id}/",
            {"main_categoryName": "Drainage"},
            format="json",
        )
        assert resp.status_code in (200, 204)

    def test_delete(self, auth_client):
        mc = MainCategory.objects.create(main_categoryName="Temp")
        resp = auth_client.delete(f"{self.BASE}{mc.unique_id}/")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestSubCategoryAPI:
    BASE = "/api/v1/grivences/sub-category/"

    def test_list_authenticated(self, auth_client):
        mc = MainCategory.objects.create(main_categoryName="Waste")
        SubCategory.objects.create(name="Overflow", mainCategory=mc)
        resp = auth_client.get(self.BASE)
        assert resp.status_code == 200

    def test_create(self, auth_client):
        mc = MainCategory.objects.create(main_categoryName="Collection Issues")
        resp = auth_client.post(
            self.BASE,
            {"name": "Late Pickup", "mainCategory": mc.unique_id},
            format="json",
        )
        assert resp.status_code in (200, 201)

    def test_retrieve(self, auth_client):
        mc = MainCategory.objects.create(main_categoryName="Bin Issues")
        sc = SubCategory.objects.create(name="Broken Bin", mainCategory=mc)
        resp = auth_client.get(f"{self.BASE}{sc.unique_id}/")
        assert resp.status_code == 200
