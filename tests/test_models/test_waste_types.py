"""Unit tests for Property and SubProperty models."""
import pytest
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


@pytest.mark.django_db
class TestPropertyModel:
    def test_create(self):
        p = Property.objects.create(property_name="Residential")
        assert p.property_name == "Residential"
        assert p.unique_id.startswith("PROPERTY-")

    def test_str(self):
        p = Property.objects.create(property_name="Commercial")
        assert "Commercial" in str(p)

    def test_default_flags(self):
        p = Property.objects.create(property_name="Industrial")
        assert p.is_active is True
        assert p.is_deleted is False

    def test_soft_delete(self):
        p = Property.objects.create(property_name="Hospital")
        p.delete()
        p.refresh_from_db()
        assert p.is_deleted is True

    def test_unique_ids_differ(self):
        p1 = Property.objects.create(property_name="Prop1")
        p2 = Property.objects.create(property_name="Prop2")
        assert p1.unique_id != p2.unique_id


@pytest.mark.django_db
class TestSubPropertyModel:
    def test_create(self):
        prop = Property.objects.create(property_name="Residential")
        sp = SubProperty.objects.create(sub_property_name="Apartment", property_id=prop)
        assert sp.sub_property_name == "Apartment"
        assert sp.unique_id.startswith("SUBPROPERTY-")

    def test_str(self):
        prop = Property.objects.create(property_name="Commercial")
        sp = SubProperty.objects.create(sub_property_name="Office", property_id=prop)
        assert "Office" in str(sp)

    def test_default_flags(self):
        prop = Property.objects.create(property_name="Industrial")
        sp = SubProperty.objects.create(sub_property_name="Factory", property_id=prop)
        assert sp.is_active is True
        assert sp.is_deleted is False

    def test_soft_delete(self):
        prop = Property.objects.create(property_name="Mixed")
        sp = SubProperty.objects.create(sub_property_name="Warehouse", property_id=prop)
        sp.delete()
        sp.refresh_from_db()
        assert sp.is_deleted is True

    def test_foreign_key_property(self):
        prop = Property.objects.create(property_name="Retail")
        sp = SubProperty.objects.create(sub_property_name="Mall", property_id=prop)
        assert sp.property_id == prop
