from app import create_app


def test_balance_sheet_route_requires_symbol():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/balance-sheet")

    assert response.status_code == 400
    body = response.get_json()
    assert body["status"] == "error"
    assert any("symbol" in error for error in body["errors"])


def test_balance_sheet_route_returns_payload(monkeypatch):
    def fake_fetch_and_build_balance_sheet(symbol):
        return {
            "status": "ok",
            "symbol": symbol,
            "data": [
                {
                    "period": "Q1",
                    "fiscalYear": 2026,
                    "fiscalQuarter": 1,
                    "currency": "IDR",
                    "auditStatus": "UNAUDITED",
                    "cash": 15544412569000,
                    "shortTermInvestments": None,
                    "accountsReceivable": 8167254545000,
                    "inventory": 2357064341000,
                    "otherCurrentAssets": 4675574950000,
                    "totalCurrentAssets": 30744306405000,
                    "propertyPlantEquipment": 67519093055000,
                    "intangibleAssets": 0,
                    "goodwill": 0,
                    "longTermInvestments": None,
                    "otherNonCurrentAssets": 0,
                    "totalNonCurrentAssets": 67519093055000,
                    "totalAssets": 98263399460000,
                    "shortTermDebt": 0,
                    "accountsPayable": 7275028032000,
                    "deferredRevenue": None,
                    "otherCurrentLiabilities": 7398168788000,
                    "totalCurrentLiabilities": 14673196820000,
                    "longTermDebt": 19313073870000,
                    "deferredTaxLiabilities": 0,
                    "otherNonCurrentLiabilities": 0,
                    "totalNonCurrentLiabilities": 19313073870000,
                    "totalLiabilities": 33986270690000,
                    "commonStock": 42830374418000,
                    "additionalPaidInCapital": -1640590489000,
                    "retainedEarnings": 16261277398000,
                    "treasuryStock": None,
                    "otherEquity": 0,
                    "minorityInterestEquity": 5214613240000,
                    "totalEquity": 64277128770000,
                    "bookValuePerShare": 389.0,
                    "netDebt": 16071109585000.0,
                    "workingCapital": 16071109585000.0
                }
            ]
        }

    monkeypatch.setattr("app.routes.fetch_and_build_balance_sheet", fake_fetch_and_build_balance_sheet)

    app = create_app()
    client = app.test_client()

    response = client.get("/api/balance-sheet?symbol=bbca")

    assert response.status_code == 200
    body = response.get_json()
    assert body["symbol"] == "BBCA"
    assert len(body["data"]) == 1
    item = body["data"][0]
    assert item["period"] == "Q1"
    assert item["fiscalYear"] == 2026
    assert item["cash"] == 15544412569000
    assert item["totalAssets"] == 98263399460000
    assert item["bookValuePerShare"] == 389.0
