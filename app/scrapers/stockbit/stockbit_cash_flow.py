from typing import Any, Dict, List
from .base_scraper import BaseStockbitScraper
from .stockbit_session import StockbitSessionHandler
from .config import CASH_FLOW_FIELDS


class StockbitCashFlowScraper(BaseStockbitScraper):
    """Scraper untuk Cash Flow"""
    
    def __init__(self, symbol: str, headless: bool = False):
        super().__init__(symbol, report_type="3", headless=headless)
        self.field_mapping = CASH_FLOW_FIELDS
        self.session_handler = None
    
    def scrape(self) -> Dict:
        """Main scraping method untuk Cash Flow"""
        try:
            print(f"[1/6] Launching browser...")
            self.launch_browser()
            self.session_handler = StockbitSessionHandler(self.page)
            
            print(f"[2/6] Navigating to {self.symbol}...")
            self.navigate_to_symbol()
            
            if self.session_handler.check_session_expired():
                if not self.session_handler.handle_session_with_retry():
                    raise ValueError("Session expired")
            
            print(f"[3/6] Selecting Cash Flow...")
            self.select_report_type("3")
            
            print(f"[4/6] Waiting for data table...")
            self.session_handler.wait_for_element_with_session_check(
                f"{DATA_TABLE_SELECTOR} tbody tr td[data-raw]",
                timeout=30000
            )
            
            self.scroll_to_table()
            
            print(f"[5/6] Extracting data...")
            raw_data = self.extract_all_data()
            periods = self.extract_periods_from_header()
            
            field_data = self._map_field_data(raw_data, periods)
            
            print(f"[6/6] Building result...")
            result_data = self._build_result(field_data, periods)
            
            return {
                "status": "ok",
                "symbol": self.symbol,
                "data": result_data
            }
            
        except Exception as exc:
            raise ValueError(f"Failed: {exc}") from exc
        finally:
            self.close_browser()
    
    def _map_field_data(self, raw_data: Dict, periods: List[Dict]) -> Dict:
        field_data = {field: {} for field in self.field_mapping.keys()}
        
        for py_name, html_name in self.field_mapping.items():
            if html_name in raw_data.get("result", {}):
                values = raw_data["result"][html_name]
                for i, val in enumerate(values):
                    if i < len(periods):
                        field_data[py_name][periods[i]["key"]] = self._parse_numeric(val)
        
        return field_data
    
    def _build_result(self, field_data: Dict, periods: List[Dict]) -> List[Dict]:
        result_data = []
        
        for p_info in periods:
            key = p_info["key"]
            
            item = {
                "period": p_info["period"],
                "fiscalYear": p_info["fiscalYear"],
                "fiscalQuarter": p_info["fiscalQuarter"],
                "currency": "IDR",
                "operatingCashFlow": field_data["operatingCashFlow"].get(key),
                "investingCashFlow": field_data["investingCashFlow"].get(key),
                "financingCashFlow": field_data["financingCashFlow"].get(key),
            }
            
            result_data.append(item)
        
        return result_data


def scrape_cash_flow(symbol: str, headless: bool = False) -> Dict:
    """Helper function untuk scrape cash flow"""
    scraper = StockbitCashFlowScraper(symbol, headless=headless)
    return scraper.scrape()