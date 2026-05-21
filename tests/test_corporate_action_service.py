from app import create_app
import app.scraper as scraper_module
import app.scrapers.corporate_action as corporate_action_module


def test_fetch_idx_corporate_action_forwards_filters(monkeypatch):
    captured = {}

    def fake_get_json_cloudscraper(url, params=None, headers=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return {
            "draw": 0,
            "recordsTotal": 1,
            "recordsFiltered": 1,
            "data": [{"KodeEmiten": "BBCA"}],
        }

    monkeypatch.setattr(corporate_action_module, "_get_json_cloudscraper", fake_get_json_cloudscraper)

    payload = scraper_module.fetch_idx_corporate_action(
        ca_type="waran",
        date_from="2026-05-01",
        date_to="2026-05-31",
        start=0,
        length=9999,
    )

    assert captured["url"].endswith("GetIssuedHistory")
    assert captured["params"] == {
        "caType": "waran",
        "dateFrom": "2026-05-01",
        "dateTo": "2026-05-31",
        "start": 0,
        "length": 9999,
    }
    assert payload["recordsTotal"] == 1
    assert payload["data"] == [{"KodeEmiten": "BBCA"}]


def test_corporate_action_route_returns_payload(monkeypatch):
    def fake_fetch_and_build_corporate_action(**kwargs):
        return {
            "draw": 0,
            "recordsTotal": 1,
            "recordsFiltered": 1,
            "data": [{"KodeEmiten": "BBCA", "JenisTindakan": "waran"}],
            "filters": kwargs,
        }

    monkeypatch.setattr("app.routes.fetch_and_build_corporate_action", fake_fetch_and_build_corporate_action)

    app = create_app()
    client = app.test_client()

    response = client.get("/api/corporate-action?caType=waran&dateFrom=2026-05-01&dateTo=2026-05-31")

    assert response.status_code == 200
    body = response.get_json()
    assert body["data"][0]["KodeEmiten"] == "BBCA"
    assert body["filters"]["ca_type"] == "waran"