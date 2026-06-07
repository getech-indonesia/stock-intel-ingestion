from app import create_app
from app.scrapers import financial_statement as financial_statement_module


def _build_financial_statement_pdf_text() -> str:
    return """
PT BANK CENTRAL ASIA Tbk DAN ENTITAS ANAK/AND SUBSIDIARIES
LAPORAN POSISI KEUANGAN KONSOLIDASIAN
31 MARET 2025 (TIDAK DIAUDIT)
DAN 31 DESEMBER 2024 (DIAUDIT)
(Dalam jutaan Rupiah, kecuali dinyatakan lain)
Catatan/Notes   31 Maret/March 2025   31 Desember/December 2024
Kas   28.032.494   29.315.878   Cash
Giro pada Bank Indonesia   56.182.969   36.408.142   Current accounts with Bank Indonesia
Penempatan pada Bank Indonesia dan bank-bank lain   25.277.033   15.714.884   Placements with Bank Indonesia and other banks
Jumlah aset   1.533.763.445   1.449.301.328   Total assets
Jumlah liabilitas   1.278.027.110   1.177.403.108   Total liabilities
Jumlah ekuitas   246.520.509   262.835.087   Total equity
LAPORAN LABA RUGI DAN PENGHASILAN KOMPREHENSIF LAIN KONSOLIDASIAN
31 MARET 2025 DAN 31 MARET 2024
Catatan/Notes   31 Maret/March 2025   31 Maret/March 2024
Pendapatan bunga dan syariah   24.366.718   22.963.761
Pendapatan bunga dan syariah - bersih   21.118.560   19.766.457
Pendapatan operasional lainnya   7.005.767   6.451.724
Beban operasional lainnya   (9.637.633)   (9.416.692)
Laba sebelum pajak penghasilan   17.455.662   15.915.029
Beban pajak penghasilan   (3.308.672)   (3.036.522)
Laba bersih   14.146.990   12.878.507
Laba bersih yang dapat diatribusikan kepada pemilik entitas induk   14.146.131   12.879.486
Kepentingan non-pengendali   859   (979)
Laba bersih per saham dasar dan dilusian   115   104
LAPORAN ARUS KAS KONSOLIDASIAN
31 MARET 2025 DAN 31 MARET 2024
Catatan/Notes   31 Maret/March 2025   31 Maret/March 2024
Kas bersih yang diperoleh dari aktivitas operasi   35.183.351   29.921.610
Kas bersih yang digunakan untuk aktivitas investasi   (25.981.888)   (10.570.212)
Kas bersih yang digunakan untuk aktivitas pendanaan   (9.307.341)   (22.412.010)
Kenaikan (penurunan) bersih kas dan setara kas   (105.878)   (3.060.612)
Kas dan setara kas pada awal periode   33.254.736   30.256.343
Kas dan setara kas pada akhir periode   33.148.858   27.195.731
""".strip()


def test_financial_statement_route_requires_symbol_and_year():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/financial-statement")

    assert response.status_code == 400
    body = response.get_json()
    assert body["status"] == "error"
    assert any("symbol" in error for error in body["errors"])
    assert any("year" in error for error in body["errors"])


def test_financial_statement_route_returns_payload(monkeypatch):
    def fake_fetch_and_build_financial_statement(symbol, year):
        return {
            "status": "ok",
            "symbol": symbol,
            "year": year,
            "income_statement": {
                "count": 1,
                "items": [
                    {
                        "period": "AUDIT",
                        "fiscalYear": year,
                        "revenue": 1000,
                    }
                ],
            },
            "balance_sheet": {
                "count": 1,
                "items": [
                    {
                        "period": "AUDIT",
                        "fiscalYear": year,
                        "totalAssets": 1400,
                    }
                ],
            },
            "cash_flow_statement": {
                "count": 1,
                "items": [
                    {
                        "period": "AUDIT",
                        "fiscalYear": year,
                        "netCashFromOperations": 570,
                    }
                ],
            },
        }

    monkeypatch.setattr("app.routes.fetch_and_build_financial_statement", fake_fetch_and_build_financial_statement)

    app = create_app()
    client = app.test_client()

    response = client.get("/api/financial-statement?symbol=bbri&year=2025")

    assert response.status_code == 200
    body = response.get_json()
    assert body["symbol"] == "BBRI"
    assert body["income_statement"]["count"] == 1
    assert body["income_statement"]["items"][0]["revenue"] == 1000
    assert body["balance_sheet"]["count"] == 1
    assert body["balance_sheet"]["items"][0]["totalAssets"] == 1400
    assert body["cash_flow_statement"]["count"] == 1
    assert body["cash_flow_statement"]["items"][0]["netCashFromOperations"] == 570


def test_scrape_financial_statement_extracts_values(monkeypatch):
    pdf_text = _build_financial_statement_pdf_text()

    monkeypatch.setattr(financial_statement_module, "fetch_financial_report_results", lambda symbol, year: [
        {
            "Report_Period": "TW1",
            "Report_Year": str(year),
            "Attachments": [
                {
                    "File_Name": "FinancialStatement-2025-I-BBRI.pdf",
                    "File_Path": "/fake/report.pdf",
                    "File_Type": ".pdf",
                }
            ],
        }
    ])
    monkeypatch.setattr(financial_statement_module, "_download_file", lambda url: b"%PDF-1.4 fake bytes")
    monkeypatch.setattr(financial_statement_module, "_extract_attachment_text", lambda file_name, content: pdf_text)

    payload = financial_statement_module.scrape_financial_statement("bbri", 2025)

    assert payload["income_statement"]["count"] == 1
    statement = payload["income_statement"]["items"][0]
    assert statement["revenue"] == 24366718000000
    assert statement["operatingIncome"] == 21118560000000
    assert statement["netIncome"] == 14146990000000
    assert statement["eps"] == 115
    assert statement["period"] == "Q1"
    assert payload["balance_sheet"]["count"] == 1
    balance_sheet = payload["balance_sheet"]["items"][0]
    assert balance_sheet["cash"] == 28032494000000
    assert balance_sheet["shortTermInvestments"] == 56182969000000
    assert balance_sheet["totalAssets"] == 1533763445000000
    assert balance_sheet["totalLiabilities"] == 1278027110000000
    assert balance_sheet["totalEquity"] == 246520509000000
    assert payload["cash_flow_statement"]["count"] == 1
    cash_flow_statement = payload["cash_flow_statement"]["items"][0]
    assert cash_flow_statement["netCashFromOperations"] == 35183351000000
    assert cash_flow_statement["netCashFromInvesting"] == -25981888000000
    assert cash_flow_statement["netCashFromFinancing"] == -9307341000000
    assert cash_flow_statement["freeCashFlow"] is None


def test_scrape_financial_statement_splits_period_from_file_name(monkeypatch):
    pdf_text = _build_financial_statement_pdf_text()

    monkeypatch.setattr(financial_statement_module, "fetch_financial_report_results", lambda symbol, year: [
        {
            "Report_Period": "Audit",
            "Report_Year": str(year),
            "Attachments": [
                {"File_Name": "Laporan Keuangan 2025 Tahunan BBCA.pdf", "File_Path": "/fake/audit.pdf", "File_Type": ".pdf"},
                {"File_Name": "FinancialStatement-2025-I-BBCA.pdf", "File_Path": "/fake/q1.pdf", "File_Type": ".pdf"},
                {"File_Name": "FinancialStatement-2025-II-BBCA.pdf", "File_Path": "/fake/q2.pdf", "File_Type": ".pdf"},
                {"File_Name": "FS BBCA 2025 III.pdf", "File_Path": "/fake/q3.pdf", "File_Type": ".pdf"},
            ],
        }
    ])
    monkeypatch.setattr(financial_statement_module, "_download_file", lambda url: b"%PDF-1.4 fake bytes")
    monkeypatch.setattr(financial_statement_module, "_extract_attachment_text", lambda file_name, content: pdf_text)

    payload = financial_statement_module.scrape_financial_statement("bbca", 2025)

    income_periods = [item.get("period") for item in payload["income_statement"]["items"]]
    balance_periods = [item.get("period") for item in payload["balance_sheet"]["items"]]
    assert payload["income_statement"]["count"] == 4
    assert payload["balance_sheet"]["count"] == 4
    assert "AUDIT" in income_periods
    assert "Q1" in income_periods
    assert "Q2" in income_periods
    assert "Q3" in income_periods
    assert "AUDIT" in balance_periods
    assert "Q1" in balance_periods
    assert "Q2" in balance_periods
    assert "Q3" in balance_periods
