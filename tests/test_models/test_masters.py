"""Unit tests for District, City, Zone, Ward, Panchayat, AreaType models."""
import pytest
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward
from app.models.masters.areatype import AreaType


@pytest.mark.django_db
class TestAreaTypeModel:
    def test_create(self, state, district, city):
        a = AreaType.objects.create(
            name="Rural",
            state_id=state,
            district_id=district,
            city_id=city,
        )
        assert a.name == "Rural"

    def test_str(self, state, district, city):
        a = AreaType.objects.create(
            name="Urban",
            state_id=state,
            district_id=district,
            city_id=city,
        )
        assert str(a) == "Urban"

    def test_default_flags(self, state, district, city):
        a = AreaType.objects.create(
            name="Semi-Urban",
            state_id=state,
            district_id=district,
            city_id=city,
        )
        assert a.is_active is True
        assert a.is_deleted is False

    def test_soft_delete(self, state, district, city):
        a = AreaType.objects.create(
            name="Coastal",
            state_id=state,
            district_id=district,
            city_id=city,
        )
        a.delete()
        a.refresh_from_db()
        assert a.is_deleted is True


@pytest.mark.django_db
class TestDistrictModel:
    def test_create(self, continent, country, state):
        d = District.objects.create(
            name="Coimbatore",
            continent_id=continent,
            country_id=country,
            state_id=state,
        )
        assert d.name == "Coimbatore"
        assert d.unique_id.startswith("DIST-")

    def test_str(self, district):
        assert "Chennai" in str(district)

    def test_default_flags(self, continent, country, state):
        d = District.objects.create(
            name="Madurai",
            continent_id=continent,
            country_id=country,
            state_id=state,
        )
        assert d.is_active is True
        assert d.is_deleted is False

    def test_foreign_key_state(self, district, state):
        assert district.state_id == state

    def test_unique_together_state_name(self, continent, country, state):
        from django.db import IntegrityError
        District.objects.create(
            name="Tiruchi",
            continent_id=continent,
            country_id=country,
            state_id=state,
        )
        with pytest.raises(IntegrityError):
            District.objects.create(
                name="Tiruchi",
                continent_id=continent,
                country_id=country,
                state_id=state,
            )


@pytest.mark.django_db
class TestCityModel:
    def test_create(self, company, project, continent, country, state, district):
        c = City.objects.create(
            name="Coimbatore City",
            continent_id=continent,
            country_id=country,
            state_id=state,
            district_id=district,
            company_id=company,
            project_id=project,
        )
        assert c.name == "Coimbatore City"
        assert c.unique_id.startswith("CITY-")

    def test_str(self, city):
        assert "Chennai" in str(city)

    def test_default_flags(self, city):
        assert city.is_active is True
        assert city.is_deleted is False

    def test_foreign_key_district(self, city, district):
        assert city.district_id == district


@pytest.mark.django_db
class TestZoneModel:
    def test_create(self, state, district, city):
        z = Zone.objects.create(
            zone_name="Zone Alpha",
            state_id=state,
            district_id=district,
            city_id=city,
        )
        assert z.zone_name == "Zone Alpha"
        assert z.unique_id.startswith("ZONE-")

    def test_default_flags(self, zone):
        assert zone.is_active is True
        assert zone.is_deleted is False

    def test_foreign_keys(self, zone, state, district, city):
        assert zone.state_id == state
        assert zone.district_id == district
        assert zone.city_id == city

    def test_optional_geo_fields(self, state, district, city):
        z = Zone.objects.create(
            zone_name="Zone Beta",
            state_id=state,
            district_id=district,
            city_id=city,
        )
        assert z.latitude is None
        assert z.longitude is None

    def test_timestamps_set_on_create(self, zone):
        assert zone.created_at is not None
        assert zone.updated_at is not None


@pytest.mark.django_db
class TestWardModel:
    def test_create(self, state, district, city, zone):
        w = Ward.objects.create(
            ward_name="Ward Alpha",
            state_id=state,
            district_id=district,
            city_id=city,
            zone_id=zone,
        )
        assert w.ward_name == "Ward Alpha"
        assert w.unique_id.startswith("WARD-")

    def test_default_flags(self, ward):
        assert ward.is_active is True
        assert ward.is_deleted is False

    def test_foreign_key_zone(self, ward, zone):
        assert ward.zone_id == zone
