from io import BytesIO

from openpyxl import Workbook

from app import create_app
from app.scrapers import income_statement as income_statement_module


def _build_income_statement_workbook() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Income Statement"

    ws.append(["Metric", 2025, 2024])
    ws.append(["Revenue", 1000, 900])
    ws.append(["COGS", 400, 350])
    ws.append(["Gross Profit", 600, 550])
    ws.append(["Operating Expenses", 120, 110])
    ws.append(["Selling Expenses", 40, 35])
    ws.append(["General Admin Expenses", 30, 28])
    ws.append(["R&D Expenses", 10, 9])
    ws.append(["Depreciation & Amortization", 15, 14])
    ws.append(["EBIT", 480, 440])
    ws.append(["EBITDA", 495, 454])
    ws.append(["Operating Income", 470, 430])
    ws.append(["Interest Expense", 20, 18])
    ws.append(["Interest Income", 5, 4])
    ws.append(["Other Non Operating Income", 7, 6])
    ws.append(["Pretax Income", 462, 422])
    ws.append(["Income Tax Expense", 92, 84])
    ws.append(["Effective Tax Rate", 19.91, 19.91])
    ws.append(["Net Income", 370, 338])
    ws.append(["Net Income Attributable", 360, 330])
    ws.append(["Minority Interest", 10, 8])
    ws.append(["EPS", 12.5, 11.2])
    ws.append(["EPS Diluted", 12.2, 11.0])
    ws.append(["Weighted Avg Shares", 300, 302])

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_income_statement_route_requires_symbol_and_year():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/income-statement")

    assert response.status_code == 400
    body = response.get_json()
    assert body["status"] == "error"
    assert any("symbol" in error for error in body["errors"])
    assert any("year" in error for error in body["errors"])


def test_income_statement_route_returns_payload(monkeypatch):
    def fake_fetch_and_build_income_statement(symbol, year):
        return {
            "status": "ok",
            "symbol": symbol,
            "year": year,
            "count": 1,
            "items": [
                {
                    "period": "AUDIT",
                    "fiscalYear": year,
                    "revenue": 1000,
                }
            ],
        }

    monkeypatch.setattr("app.routes.fetch_and_build_income_statement", fake_fetch_and_build_income_statement)

    app = create_app()
    client = app.test_client()

    response = client.get("/api/income-statement?symbol=bbri&year=2025")

    assert response.status_code == 200
    body = response.get_json()
    assert body["symbol"] == "BBRI"
    assert body["count"] == 1
    assert body["items"][0]["revenue"] == 1000


def test_scrape_income_statement_extracts_values(monkeypatch):
    workbook_bytes = _build_income_statement_workbook()

    monkeypatch.setattr(income_statement_module, "fetch_financial_report_results", lambda symbol, year: [
        {
            "Report_Period": "Audit",
            "Report_Year": str(year),
            "Attachments": [
                {
                    "File_Name": "FinancialStatement-2025-Tahunan-BBRI.xlsx",
                    "File_Path": "/fake/report.xlsx",
                    "File_Type": ".xlsx",
                }
            ],
        }
    ])
    monkeypatch.setattr(income_statement_module, "_download_file", lambda url: workbook_bytes)

    payload = income_statement_module.scrape_income_statement("bbri", 2025)

    assert payload["count"] == 1
    statement = payload["items"][0]
    assert statement["revenue"] == 1000
    assert statement["grossProfit"] == 600
    assert statement["netIncome"] == 370
    assert statement["eps"] == 12.5
    assert statement["period"] == "AUDIT"


def test_scrape_income_statement_splits_period_from_file_name(monkeypatch):
    workbook_bytes = _build_income_statement_workbook()

    monkeypatch.setattr(income_statement_module, "fetch_financial_report_results", lambda symbol, year: [
        {
            "Report_Period": "Audit",
            "Report_Year": str(year),
            "Attachments": [
                {"File_Name": "FinancialStatement-2025-Tahunan-BBCA.xlsx", "File_Path": "/fake/audit.xlsx", "File_Type": ".xlsx"},
                {"File_Name": "FinancialStatement-2025-I-BBCA.xlsx", "File_Path": "/fake/q1.xlsx", "File_Type": ".xlsx"},
                {"File_Name": "FinancialStatement-2025-II-BBCA.xlsx", "File_Path": "/fake/q2.xlsx", "File_Type": ".xlsx"},
                {"File_Name": "FinancialStatement-2025-III-BBCA.xlsx", "File_Path": "/fake/q3.xlsx", "File_Type": ".xlsx"},
            ],
        }
    ])
    monkeypatch.setattr(income_statement_module, "_download_file", lambda url: workbook_bytes)

    payload = income_statement_module.scrape_income_statement("bbca", 2025)

    periods = [item.get("period") for item in payload["items"]]
    assert payload["count"] == 4
    assert "AUDIT" in periods
    assert "Q1" in periods
    assert "Q2" in periods
    assert "Q3" in periods