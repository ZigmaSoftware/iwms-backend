"""Unit tests for Continent, Country, and State models."""
import pytest
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State


@pytest.mark.django_db
class TestContinentModel:
    def test_create(self):
        c = Continent.objects.create(name="Europe")
        assert c.name == "Europe"
        assert c.unique_id.startswith("CONT-")

    def test_str(self):
        c = Continent.objects.create(name="Africa")
        assert str(c) == "Africa"

    def test_default_is_active(self):
        c = Continent.objects.create(name="Oceania")
        assert c.is_active is True

    def test_default_is_not_deleted(self):
        c = Continent.objects.create(name="Americas")
        assert c.is_deleted is False

    def test_soft_delete(self):
        c = Continent.objects.create(name="Antarctica")
        c.delete()
        c.refresh_from_db()
        assert c.is_deleted is True

    def test_unique_id_is_primary_key(self):
        c = Continent.objects.create(name="North America")
        assert Continent.objects.get(pk=c.unique_id) == c

    def test_ordering_alphabetical(self):
        Continent.objects.create(name="Zzz")
        Continent.objects.create(name="Aaa")
        names = list(Continent.objects.values_list("name", flat=True))
        assert names == sorted(names)

    def test_unique_id_auto_generated(self):
        c1 = Continent.objects.create(name="C1")
        c2 = Continent.objects.create(name="C2")
        assert c1.unique_id != c2.unique_id


@pytest.mark.django_db
class TestCountryModel:
    def test_create(self, continent):
        c = Country.objects.create(
            name="France",
            continent_id=continent,
            currency="EUR",
            mob_code="+33",
        )
        assert c.name == "France"
        assert c.unique_id.startswith("COUNTRY-")

    def test_str(self, continent):
        c = Country.objects.create(name="Germany", continent_id=continent)
        assert str(c) == "Germany"

    def test_default_flags(self, continent):
        c = Country.objects.create(name="Spain", continent_id=continent)
        assert c.is_active is True
        assert c.is_deleted is False

    def test_soft_delete(self, continent):
        c = Country.objects.create(name="Italy", continent_id=continent)
        c.delete()
        c.refresh_from_db()
        assert c.is_deleted is True

    def test_foreign_key_to_continent(self, continent):
        c = Country.objects.create(name="Portugal", continent_id=continent)
        assert c.continent_id == continent

    def test_optional_fields_nullable(self, continent):
        c = Country.objects.create(name="Greece", continent_id=continent)
        assert c.currency is None
        assert c.mob_code is None

    def test_ordering_alphabetical(self, continent):
        Country.objects.create(name="Zimbabwe", continent_id=continent)
        Country.objects.create(name="Albania", continent_id=continent)
        names = list(Country.objects.values_list("name", flat=True))
        assert names == sorted(names)


@pytest.mark.django_db
class TestStateModel:
    def test_create(self, continent, country):
        s = State.objects.create(
            name="Kerala",
            label="KL",
            continent_id=continent,
            country_id=country,
        )
        assert s.name == "Kerala"
        assert s.label == "KL"
        assert s.unique_id.startswith("STATE-")

    def test_str(self, continent, country):
        s = State.objects.create(
            name="Karnataka",
            label="KA",
            continent_id=continent,
            country_id=country,
        )
        assert "Karnataka" in str(s)

    def test_default_flags(self, continent, country):
        s = State.objects.create(
            name="Goa",
            label="GA",
            continent_id=continent,
            country_id=country,
        )
        assert s.is_active is True
        assert s.is_deleted is False

    def test_soft_delete(self, state):
        state.delete()
        state.refresh_from_db()
        assert state.is_deleted is True

    def test_foreign_keys(self, continent, country, state):
        assert state.continent_id == continent
        assert state.country_id == country
