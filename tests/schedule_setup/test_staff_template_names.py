import pytest


@pytest.mark.django_db
def test_staff_template_api_includes_driver_and_operator_names(
    auth_client, staff_template, driver, operator
):
    response = auth_client.get(
        f"/api/v1/schedule-setup/staff-templates/{staff_template.unique_id}/"
    )

    assert response.status_code == 200
    assert response.data["driver_id"] == driver.staff_unique_id
    assert response.data["operator_id"] == operator.staff_unique_id
    assert response.data["driver_name"] == driver.employee_name
    assert response.data["operator_name"] == operator.employee_name

    list_response = auth_client.get("/api/v1/schedule-setup/staff-templates/")
    assert list_response.status_code == 200
    team = next(
        row for row in list_response.data["results"]
        if row["unique_id"] == staff_template.unique_id
    )
    assert team["driver_name"] == driver.employee_name
    assert team["operator_name"] == operator.employee_name
