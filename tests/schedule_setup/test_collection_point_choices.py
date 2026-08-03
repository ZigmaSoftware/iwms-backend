"""Tests for Collection_point collection_type restriction (bin + bulk only)."""
import pytest
from django.urls import reverse

from app.models.schedule_masters.collection_point import Collection_point
from app.serializers.core_modules.schedule_setup.collection_point_serializer import (
    CollectionPointSerializer,
)


@pytest.fixture
def panchayat(db, company, project, state, district, city):
    from app.models.masters.panchayat import Panchayat
    return Panchayat.objects.create(
        panchayat_name="CP Choices Panchayat",
        company_id=company,
        project_id=project,
        state_id=state,
        district_id=district,
        city_id=city,
    )


def _cp_payload(company, project, state, district, city, panchayat, cp_name, collection_type):
    return {
        "cp_name": cp_name,
        "company_id": company.unique_id,
        "project_id": project.unique_id,
        "state_id": state.unique_id,
        "city_id": city.unique_id,
        "district_id": district.unique_id,
        "panchayat_id": panchayat.unique_id,
        "collection_type": collection_type,
        "latitude": "13.0827",
        "longitude": "80.2707",
    }


@pytest.mark.django_db
class TestCollectionPointModelChoices:
    def test_model_defines_bulk_choice(self):
        assert Collection_point.COLLECTION_TYPE_BULK == "bulk_waste_collection"
        assert ("bulk_waste_collection", "Bulk Waste Collection") in Collection_point.COLLECTION_TYPE_CHOICES

    def test_legacy_choices_retained(self):
        assert Collection_point.COLLECTION_TYPE_BIN == "bin_collection"
        assert Collection_point.COLLECTION_TYPE_HOUSEHOLD == "household_collection"
        assert ("household_collection", "Household Collection") in Collection_point.COLLECTION_TYPE_CHOICES

    def test_cp_choices_exclude_household(self):
        assert Collection_point.COLLECTION_TYPE_CP_CHOICES == [
            (Collection_point.COLLECTION_TYPE_BIN, "Bin Collection"),
            (Collection_point.COLLECTION_TYPE_BULK, "Bulk Waste Collection"),
        ]


@pytest.mark.django_db
class TestCollectionPointSerializerChoices:
    def test_serializer_field_exposes_bin_and_bulk_only(self):
        field = CollectionPointSerializer().fields["collection_type"]
        allowed = {value for value, _ in field.choices.items()}
        assert allowed == {"bin_collection", "bulk_waste_collection"}
        assert "household_collection" not in allowed

    def test_create_rejects_household(self, company, project, state, district, city, panchayat):
        serializer = CollectionPointSerializer(
            data=_cp_payload(
                company, project, state, district, city, panchayat,
                cp_name="Household Blocked CP",
                collection_type=Collection_point.COLLECTION_TYPE_HOUSEHOLD,
            )
        )
        assert not serializer.is_valid()
        assert "collection_type" in serializer.errors

    def test_create_accepts_bin(self, company, project, state, district, city, panchayat):
        serializer = CollectionPointSerializer(
            data=_cp_payload(
                company, project, state, district, city, panchayat,
                cp_name="Bin CP",
                collection_type=Collection_point.COLLECTION_TYPE_BIN,
            )
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["collection_type"] == "bin_collection"

    def test_create_accepts_bulk(self, company, project, state, district, city, panchayat):
        serializer = CollectionPointSerializer(
            data=_cp_payload(
                company, project, state, district, city, panchayat,
                cp_name="Bulk CP",
                collection_type=Collection_point.COLLECTION_TYPE_BULK,
            )
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["collection_type"] == "bulk_waste_collection"


@pytest.mark.django_db
class TestCollectionPointLegacyHouseholdRows:
    def test_legacy_household_row_is_loadable(self, company, project, state, district, city, panchayat):
        cp = Collection_point.objects.create(
            cp_name="Legacy Household CP",
            company_id=company,
            project_id=project,
            state_id=state,
            city_id=city,
            district_id=district,
            panchayat_id=panchayat,
            collection_type=Collection_point.COLLECTION_TYPE_HOUSEHOLD,
            latitude="13.0827",
            longitude="80.2707",
        )
        serializer = CollectionPointSerializer(cp)
        assert serializer.data["collection_type"] == "household_collection"


@pytest.mark.django_db
class TestCollectionPointChoicesEndpoint:
    def test_collection_type_choices_endpoint(self, auth_client):
        url = reverse("schedule-setup-collection-points-collection-type-choices")
        resp = auth_client.get(url)
        assert resp.status_code == 200
        values = {item["value"] for item in resp.data}
        assert values == {"bin_collection", "bulk_waste_collection"}

    def test_collection_type_choices_labels(self, auth_client):
        url = reverse("schedule-setup-collection-points-collection-type-choices")
        resp = auth_client.get(url)
        by_value = {item["value"]: item["label"] for item in resp.data}
        assert by_value["bin_collection"] == "Bin Collection"
        assert by_value["bulk_waste_collection"] == "Bulk Waste Collection"
