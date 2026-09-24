"""API tests for ContractorUserType endpoint — CRUD operations."""
import pytest
from app.models.role_assigns.userType import UserType
from app.models.role_assigns.contractorUserType import ContractorUserType

BASE = "/api/v1/role-assigns/contractorusertypes/"


def response_items(resp):
    data = resp.data
    return data.get("results", data) if isinstance(data, dict) else data


@pytest.fixture
def contractor_user_type(db):
    return UserType.objects.create(name="contractor")


@pytest.mark.django_db
class TestContractorUserTypeAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200

    def test_list_returns_display_name_for_contractor_roles(
        self,
        auth_client,
        contractor_user_type,
    ):
        ContractorUserType.objects.create(
            name="contractor_admin",
            usertype_id=contractor_user_type.unique_id,
        )
        resp = auth_client.get(BASE)

        assert resp.status_code == 200
        assert any(
            item["name"] == "Contractor Admin"
            for item in response_items(resp)
        )

    def test_list_returns_usertype_id_and_name(
        self,
        auth_client,
        contractor_user_type,
    ):
        role = ContractorUserType.objects.create(
            name="contractor_driver",
            usertype_id=contractor_user_type.unique_id,
        )
        resp = auth_client.get(BASE)

        assert resp.status_code == 200
        row = next(item for item in response_items(resp) if item["unique_id"] == role.unique_id)
        assert row["usertype_id"] == contractor_user_type.unique_id
        assert row["usertype_name"] == contractor_user_type.name


@pytest.mark.django_db
class TestContractorUserTypeAPICreate:
    def test_create_returns_success(self, auth_client, contractor_user_type):
        resp = auth_client.post(
            BASE,
            {"name": "contractor_admin", "usertype_id": contractor_user_type.pk},
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestContractorUserTypeAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, contractor_user_type):
        cut = ContractorUserType.objects.create(name="contractor_supervisor", usertype_id=contractor_user_type.unique_id)
        resp = auth_client.get(f"{BASE}{cut.unique_id}/")
        assert resp.status_code == 200
        assert resp.data["name"] == "Contractor Supervisor"


@pytest.mark.django_db
class TestContractorUserTypeAPIUpdate:
    def test_patch_returns_success(self, auth_client, contractor_user_type):
        cut = ContractorUserType.objects.create(name="contractor_driver", usertype_id=contractor_user_type.unique_id)
        resp = auth_client.patch(
            f"{BASE}{cut.unique_id}/", {"name": "contractor_worker"}, format="json"
        )
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestContractorUserTypeAPIDelete:
    def test_delete_returns_success(self, auth_client, contractor_user_type):
        cut = ContractorUserType.objects.create(name="contractor_operator", usertype_id=contractor_user_type.unique_id)
        resp = auth_client.delete(f"{BASE}{cut.unique_id}/")
        assert resp.status_code in (200, 204)
