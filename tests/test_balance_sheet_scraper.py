from types import SimpleNamespace

from app.scrapers.stockbit.stockbit_balance_sheet import StockbitBalanceSheetScraper


def test_balance_sheet_scrape_retries_after_session_expired(monkeypatch):
    scraper = StockbitBalanceSheetScraper("bbca")
    calls = {"login": 0, "navigate": 0, "select": 0, "scrape_once": 0}

    class FakeSessionHandler:
        def __init__(self, page):
            self.page = page

        def is_login_page(self):
            return False

        def check_session_expired(self):
            return False

        def wait_for_manual_login(self, timeout=300):
            calls["login"] += 1
            return True

        def wait_for_element_with_session_check(self, selector, timeout=30000, state="visible"):
            return True

    def fake_launch_browser(self):
        self.page = SimpleNamespace(wait_for_timeout=lambda timeout: None)

    def fake_close_browser(self):
        return None

    def fake_navigate_to_symbol(self):
        calls["navigate"] += 1

    def fake_select_report_type(self, report_type):
        calls["select"] += 1

    def fake_scrape_once(self):
        calls["scrape_once"] += 1
        if calls["scrape_once"] == 1:
            raise ValueError("Session expired")
        return {
            "status": "ok",
            "symbol": self.symbol,
            "data": [
                {
                    "period": "Q1",
                    "fiscalYear": 2026,
                    "fiscalQuarter": 1,
                    "currency": "IDR",
                }
            ],
        }

    monkeypatch.setattr(
        "app.scrapers.stockbit.stockbit_balance_sheet.StockbitSessionHandler",
        FakeSessionHandler,
    )
    monkeypatch.setattr(StockbitBalanceSheetScraper, "launch_browser", fake_launch_browser)
    monkeypatch.setattr(StockbitBalanceSheetScraper, "close_browser", fake_close_browser)
    monkeypatch.setattr(StockbitBalanceSheetScraper, "navigate_to_symbol", fake_navigate_to_symbol)
    monkeypatch.setattr(StockbitBalanceSheetScraper, "select_report_type", fake_select_report_type)
    monkeypatch.setattr(StockbitBalanceSheetScraper, "_scrape_once", fake_scrape_once)

    result = scraper.scrape()

    assert result["status"] == "ok"
    assert result["symbol"] == "BBCA"
    assert calls["scrape_once"] == 2
    assert calls["login"] == 1
    assert calls["navigate"] == 1
    assert calls["select"] == 1
