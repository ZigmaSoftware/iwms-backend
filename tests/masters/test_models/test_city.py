"""Unit tests for City model — CRUD + constraints."""
import pytest
from app.models.masters.city import City


@pytest.mark.django_db
class TestCityCreate:
    def test_basic_create(self, company, project, continent, country, state, district):
        c = City.objects.create(
            name="Coimbatore City",
            continent_id=continent.unique_id, country_id=country.unique_id,
            state_id=state.unique_id, district_id=district.unique_id,
            company_id=company.unique_id, project_id=project.unique_id,
        )
        assert c.name == "Coimbatore City"

    def test_unique_id_prefix(self, city):
        assert city.unique_id.startswith("CITY-")

    def test_str_contains_name(self, city):
        assert "Chennai" in str(city)

    def test_foreign_key_district(self, city, district):
        assert city.district_id == district.unique_id


@pytest.mark.django_db
class TestCityDefaults:
    def test_is_active_default_true(self, city):
        assert city.is_active is True

    def test_is_deleted_default_false(self, city):
        assert city.is_deleted is False


@pytest.mark.django_db
class TestCitySoftDelete:
    def test_soft_delete(self, city):
        city.delete()
        city.refresh_from_db()
        assert city.is_deleted is True


@pytest.mark.django_db
class TestCityUpdate:
    def test_update_name(self, city):
        city.name = "Updated City"
        city.save()
        city.refresh_from_db()
        assert city.name == "Updated City"
