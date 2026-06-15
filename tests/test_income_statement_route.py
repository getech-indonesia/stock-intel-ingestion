from app import create_app


def test_income_statement_route_requires_symbol():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/income-statement")

    assert response.status_code == 400
    body = response.get_json()
    assert body["status"] == "error"
    assert any("symbol" in error for error in body["errors"])


def test_income_statement_route_returns_payload(monkeypatch):
    def fake_fetch_and_build_income_statement(symbol):
        return {
            "status": "ok",
            "symbol": symbol,
            "period": "Q1",
            "fiscalYear": 2026,
            "fiscalQuarter": 1,
            "periodEndDate": "2026-03-31",
            "currency": "IDR",
            "auditStatus": "UNAUDITED",
            "revenue": 15492710000000,
            "revenueGrowthYoY": None,
            "cogs": -12682992000000,
            "grossProfit": 40155032000000,
            "operatingExpenses": -20095161000000,
            "sellingExpenses": None,
            "generalAdminExpenses": -7911245000000,
            "rdExpenses": None,
            "depreciationAmort": None,
            "ebit": None,
            "ebitda": 21774654000000,
            "operatingIncome": None,
            "interestExpense": -12265296000000,
            "interestIncome": 49133641000000,
            "otherNonOperatingIncome": -74243000000,
            "pretaxIncome": 19985628000000,
            "incomeTaxExpense": -4351779000000,
            "effectiveTaxRate": None,
            "netIncome": 15633849000000,
            "netIncomeAttributable": 15492710000000,
            "minorityInterest": 141139000000,
            "eps": 102.22,
            "epsDiluted": None,
            "sharesWeightedAvg": 151559001604,
        }

    monkeypatch.setattr("app.routes.fetch_and_build_income_statement", fake_fetch_and_build_income_statement)

    app = create_app()
    client = app.test_client()

    response = client.get("/api/income-statement?symbol=bbri")

    assert response.status_code == 200
    body = response.get_json()
    assert body["symbol"] == "BBRI"
    assert body["period"] == "Q1"
    assert body["fiscalYear"] == 2026
    assert body["revenue"] == 15492710000000
    assert body["eps"] == 102.22
