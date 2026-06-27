from app import create_app
import pytest

def test_extract_xbrl_placeholder():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/extract-xbrl")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert "XBRL" in body["message"]

    response_post = client.post("/api/extract-xbrl")
    assert response_post.status_code == 200
    body_post = response_post.get_json()
    assert body_post["status"] == "ok"


def test_extract_financial_report_requires_url():
    app = create_app()
    client = app.test_client()

    # GET request missing URL
    response = client.get("/api/extract-financial-report")
    assert response.status_code == 400
    assert "url" in response.get_json()["message"]

    # POST request missing URL
    response_post = client.post("/api/extract-financial-report", json={})
    assert response_post.status_code == 400
    assert "url" in response_post.get_json()["message"]


def test_extract_financial_report_success(monkeypatch):
    expected_response = {
        "symbol": "BBCA",
        "confident": 95,
        "incomeStatements": [
            {
                "period": "Q1",
                "fiscalYear": 2026,
                "fiscalQuarter": 1,
                "periodEndDate": "2026-03-31",
                "currency": "IDR",
                "auditStatus": "UNAUDITED",
                "revenue": 1000000000000,
                "revenueGrowthYoY": None,
                "cogs": None,
                "grossProfit": None,
                "operatingExpenses": None,
                "sellingExpenses": None,
                "generalAdminExpenses": None,
                "rdExpenses": None,
                "depreciationAmort": None,
                "ebit": None,
                "ebitda": None,
                "operatingIncome": None,
                "interestExpense": None,
                "interestIncome": None,
                "otherNonOperatingIncome": None,
                "pretaxIncome": None,
                "incomeTaxExpense": None,
                "effectiveTaxRate": None,
                "netIncome": 100000000000,
                "netIncomeAttributable": None,
                "minorityInterest": None,
                "eps": None,
                "epsDiluted": None,
                "sharesWeightedAvg": None
            }
        ],
        "balanceSheets": [],
        "cashFlows": []
    }

    def mock_extract(pdf_url):
        assert pdf_url == "https://example.com/report.pdf"
        return expected_response

    monkeypatch.setattr(
        "app.services.pdf_extractor_service.extract_financial_report_from_pdf",
        mock_extract
    )

    app = create_app()
    client = app.test_client()

    # Test via GET
    response = client.get("/api/extract-financial-report?url=https://example.com/report.pdf")
    assert response.status_code == 200
    body = response.get_json()
    assert body["symbol"] == "BBCA"
    assert body["confident"] == 95
    assert len(body["incomeStatements"]) == 1
    assert body["incomeStatements"][0]["revenue"] == 1000000000000

    # Test via POST json
    response_post = client.post(
        "/api/extract-financial-report",
        json={"url": "https://example.com/report.pdf"}
    )
    assert response_post.status_code == 200
    body_post = response_post.get_json()
    assert body_post["symbol"] == "BBCA"

    # Test via POST form
    response_form = client.post(
        "/api/extract-financial-report",
        data={"url": "https://example.com/report.pdf"}
    )
    assert response_form.status_code == 200
    body_form = response_form.get_json()
    assert body_form["symbol"] == "BBCA"
