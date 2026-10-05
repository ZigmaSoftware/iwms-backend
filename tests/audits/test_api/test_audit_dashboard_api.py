"""Audit Dashboard: per-trail KPIs, daily trend, breakdown and rows over a
7/30/90-day window, confined to the caller's tenancy."""
from datetime import timedelta

import pytest
from django.utils import timezone

BASE = "/api/v1/audits/audit-dashboard/"


def _common(company, project, method, days_ago=0, user="admin", **extra):
    from app.utils.common_audit import CommonAudit

    row = CommonAudit.objects.create(
        module_name="masters",
        endpoint_name="bins",
        method=method,
        object_id=extra.pop("object_id", "BIN-1"),
        company_unique_id=company.unique_id,
        company_name=company.name,
        project_unique_id=project.unique_id,
        project_name=project.name,
        createdBy=user,
        created_by_name=user,
        **extra,
    )
    CommonAudit.objects.filter(pk=row.pk).update(createdAt=timezone.now() - timedelta(days=days_ago))
    return row


@pytest.fixture
def common_rows(db, company, project):
    return [
        _common(company, project, "POST", user="s.priya"),
        _common(company, project, "PATCH", user="r.kumar", object_id="BIN-9171"),
        _common(company, project, "PUT", days_ago=2, user="r.kumar"),
        _common(company, project, "DELETE", days_ago=3, user="k.devi"),
        _common(company, project, "DOWNLOAD", days_ago=3, user="k.devi"),
        # Outside the 7-day window, inside the previous one.
        _common(company, project, "POST", days_ago=10),
    ]


@pytest.mark.django_db
class TestSummary:
    def test_common_kpis_trend_and_breakdown(self, auth_client, common_rows):
        resp = auth_client.get(f"{BASE}summary/", {"module": "common", "days": 7})

        assert resp.status_code == 200
        body = resp.json()
        assert body["days"] == 7
        assert body["kpis"] == {"total": 5, "updates": 2, "deletions": 1, "active_users": 3}
        assert body["previous_total"] == 1
        assert len(body["trend"]) == 7
        assert sum(d["count"] for d in body["trend"]) == 5
        assert body["trend"][-1] == {"date": timezone.localdate().isoformat(), "count": 2}
        assert {s["key"]: s["count"] for s in body["breakdown"]} == {
            "CREATE": 1, "UPDATE": 2, "DELETE": 1, "OTHER": 1,
        }

    def test_unknown_days_fall_back_to_30(self, auth_client, common_rows):
        body = auth_client.get(f"{BASE}summary/", {"module": "common", "days": 12}).json()
        assert body["days"] == 30
        assert body["kpis"]["total"] == 6

    def test_unknown_module_is_rejected(self, auth_client):
        assert auth_client.get(f"{BASE}summary/", {"module": "nope"}).status_code == 400

    def test_login_success_rate(self, auth_client, company):
        from app.models.superadmin.audits.loginAudit import LoginAudit

        for ok in (True, True, True, False):
            LoginAudit.objects.create(
                company_id=company.unique_id, username="admin", success=ok,
                user_agent="Mozilla/5.0 (Linux; Android 14)",
            )

        body = auth_client.get(f"{BASE}summary/", {"module": "login", "days": 7}).json()
        assert body["kpis"] == {"total": 4, "success_rate": 75, "failed": 1, "unique_users": 1}

        rows = auth_client.get(f"{BASE}records/", {"module": "login", "days": 7}).json()["results"]
        assert rows[0]["device"] == "Android"

    @pytest.mark.parametrize("module", ["access", "route", "complaint"])
    def test_empty_trails_summarise(self, auth_client, module):
        resp = auth_client.get(f"{BASE}summary/", {"module": module, "days": 7})
        assert resp.status_code == 200
        assert resp.json()["kpis"]["total"] == 0
        assert resp.json()["breakdown"] == []


@pytest.mark.django_db
class TestRecords:
    def test_rows_newest_first_within_window(self, auth_client, common_rows):
        body = auth_client.get(f"{BASE}records/", {"module": "common", "days": 7, "limit": 10}).json()

        assert body["count"] == 5
        dates = [r["date"] for r in body["results"]]
        assert dates == sorted(dates, reverse=True)
        assert {r["action"] for r in body["results"]} == {"CREATE", "UPDATE", "DELETE", "OTHER"}

    def test_search_narrows_rows(self, auth_client, common_rows):
        body = auth_client.get(f"{BASE}records/", {"module": "common", "days": 7, "search": "9171"}).json()
        assert [r["record"] for r in body["results"]] == ["BIN-9171"]

    def test_project_filter(self, auth_client, common_rows, company):
        from app.models.superadmin_masters.project import Project

        other = Project.objects.create(name="Other", company_id=company.unique_id)
        body = auth_client.get(f"{BASE}records/", {"module": "common", "project_id": other.unique_id}).json()
        assert body["count"] == 0


@pytest.mark.django_db
def test_filter_options_lists_projects_with_company(auth_client, company, project):
    body = auth_client.get(f"{BASE}filter-options/").json()

    assert {"unique_id": company.unique_id, "name": company.name} in body["companies"]
    row = next(p for p in body["projects"] if p["unique_id"] == project.unique_id)
    assert row["company_name"] == company.name


@pytest.mark.django_db
def test_requires_authentication(api_client):
    assert api_client.get(f"{BASE}summary/").status_code in (401, 403)
