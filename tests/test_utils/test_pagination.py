"""Tests for the shared LimitOffsetWithPage pagination class."""
from decimal import Decimal

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from app.utils.pagination import LimitOffsetWithPage
from app.viewsets.superadmin.staff_management.staffcreation_viewset import StaffcreationViewset


class TestLimitOffsetWithPageUnit:
    def setup_method(self):
        self.factory = APIRequestFactory()

    def test_page_parameter_returns_expected_slice_and_metadata(self):
        request = Request(self.factory.get("/", {"page": 2, "limit": 3}))
        paginator = LimitOffsetWithPage()

        page = paginator.paginate_queryset(list(range(8)), request)
        response = paginator.get_paginated_response(page)

        assert page == [3, 4, 5]
        assert response.data["count"] == 8
        assert response.data["page"] == 2
        assert response.data["total_pages"] == 3

    def test_invalid_page_falls_back_to_first_page(self):
        request = Request(self.factory.get("/", {"page": "invalid", "limit": 2}))
        paginator = LimitOffsetWithPage()

        page = paginator.paginate_queryset(list(range(5)), request)
        response = paginator.get_paginated_response(page)

        assert page == [0, 1]
        assert response.data["page"] == 1

    def test_staff_creation_explicitly_remains_unpaginated(self):
        assert StaffcreationViewset.pagination_class is None


BASE = "/api/v1/common-masters/continents/"


@pytest.mark.django_db
class TestSharedPaginationEnvelope:
    """Integration coverage: the shared pagination contract through a real,
    non-staff endpoint (view + serializer + DEFAULT_FILTER_BACKENDS +
    DEFAULT_PAGINATION_CLASS), not just the paginator class in isolation."""

    @pytest.fixture(autouse=True)
    def _seed_continents(self, db):
        from app.models.common_masters.continent import Continent

        self.continents = [
            Continent.objects.create(name=f"Continent {i}") for i in range(5)
        ]

    def test_default_request_is_paginated(self, auth_client):
        resp = auth_client.get(BASE, {"limit": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert set(["count", "next", "previous", "page", "total_pages", "results"]) <= set(data.keys())
        assert data["count"] == 5
        assert data["page"] == 1
        assert data["total_pages"] == 3
        assert len(data["results"]) == 2

    def test_page_query_param_moves_to_second_page(self, auth_client):
        resp = auth_client.get(BASE, {"limit": 2, "page": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
        assert len(data["results"]) == 2

    def test_last_page_returns_remainder(self, auth_client):
        resp = auth_client.get(BASE, {"limit": 2, "page": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 3
        assert len(data["results"]) == 1
        assert data["next"] is None


@pytest.mark.django_db
class TestStaffCreationRemainsUnpaginated:
    def test_staff_list_response_is_not_paginated(self, auth_client):
        resp = auth_client.get("/api/v1/staff-creations/staffcreation/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
