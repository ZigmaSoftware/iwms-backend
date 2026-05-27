"""Unit tests for WardCollection model — class-level checks.

Note: Full CRUD tests for WardCollection require TripDefinition → RoutePlan →
VehicleCreation → StaffTemplate chain. These are covered by integration tests.
"""
import pytest
from app.models.collections.ward_wise_collection import WardCollection


@pytest.mark.django_db
class TestWardCollectionModel:
    def test_unique_id_default_generator_format(self):
        from app.models.collections.ward_wise_collection import generate_ward_collection_id
        uid = generate_ward_collection_id()
        assert uid.startswith("WCOL-")

    def test_model_meta_has_expected_fields(self):
        field_names = {f.name for f in WardCollection._meta.get_fields()}
        assert "ward_id" in field_names
        assert "waste_type_id" in field_names
        assert "collection_date" in field_names
        assert "is_active" in field_names
        assert "is_deleted" in field_names

    def test_model_inherits_from_base_master(self):
        from app.utils.base_models import BaseMaster
        assert issubclass(WardCollection, BaseMaster)
