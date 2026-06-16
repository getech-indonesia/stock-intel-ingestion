from typing import Any, Dict, List
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .base_scraper import BaseStockbitScraper
from .stockbit_session import StockbitSessionHandler
from .config import INCOME_STATEMENT_FIELDS, DATA_TABLE_SELECTOR


class StockbitIncomeStatementScraper(BaseStockbitScraper):
    """Scraper untuk Income Statement"""
    
    def __init__(self, symbol: str, headless: bool = False):
        super().__init__(symbol, report_type="1", headless=headless)
        self.field_mapping = INCOME_STATEMENT_FIELDS
        self.session_handler = None
    
    def scrape(self) -> Dict:
        """Main scraping method untuk Income Statement"""
        try:
            # Launch browser
            print(f"[1/7] Launching browser...")
            self.launch_browser()
            self.session_handler = StockbitSessionHandler(self.page)
            
            # Navigate
            print(f"[2/7] Navigating to {self.symbol}...")
            self.navigate_to_symbol()
            
            # Check session setelah navigate
            if self.session_handler.check_session_expired():
                if not self.session_handler.handle_session_with_retry():
                    raise ValueError("Session expired dan user tidak login")
            
            # Select Income Statement
            print(f"[3/7] Selecting Income Statement...")
            self.select_report_type("1")
            
            # Wait for table
            print(f"[4/7] Waiting for data table...")
            self.session_handler.wait_for_element_with_session_check(
                f"{DATA_TABLE_SELECTOR} tbody tr td[data-raw]",
                timeout=30000
            )
            print("   Table data detected!")
            
            # Scroll to table
            self.scroll_to_table()
            
            # Extract data
            print(f"[5/7] Extracting data...")
            raw_data = self.extract_all_data()
            periods = self.extract_periods_from_header()
            
            print(f"   Found {len(periods)} periods: {[p['key'] for p in periods[:5]]}...")
            
            # Map data
            field_data = self._map_field_data(raw_data, periods)
            
            # Build result
            print(f"[6/7] Building result...")
            result_data = self._build_result(field_data, periods)
            
            print(f"[7/7] Done! Extracted {len(result_data)} periods")
            
            return {
                "status": "ok",
                "symbol": self.symbol,
                "data": result_data
            }
            
        except PlaywrightTimeoutError as exc:
            raise ValueError(f"Timeout: {exc}") from exc
        except Exception as exc:
            raise ValueError(f"Failed: {exc}") from exc
        finally:
            self.close_browser()
    
    def _map_field_data(
        self, 
        raw_data: Dict, 
        periods: List[Dict]
    ) -> Dict[str, Dict[str, Any]]:
        """Map raw data ke field dictionary"""
        field_data = {field: {} for field in self.field_mapping.keys()}
        
        for py_name, html_name in self.field_mapping.items():
            if html_name in raw_data.get("result", {}):
                values = raw_data["result"][html_name]
                for i, val in enumerate(values):
                    if i < len(periods):
                        field_data[py_name][periods[i]["key"]] = self._parse_numeric(val)
            else:
                print(f"   WARNING: Row '{html_name}' not found")
        
        return field_data
    
    def _build_result(
        self, 
        field_data: Dict[str, Dict[str, Any]], 
        periods: List[Dict]
    ) -> List[Dict]:
        """Build result list dari field data"""
        result_data = []
        
        for p_info in periods:
            key = p_info["key"]
            
            # Calculate YoY growth
            prev_year = p_info["fiscalYear"] - 1
            prev_key = f"{p_info['period']}_{prev_year}"
            
            current_rev = field_data["revenue"].get(key)
            prev_rev = field_data["revenue"].get(prev_key)
            revenue_growth_yoy = self._calculate_revenue_growth_yoy(current_rev, prev_rev)
            
            # Calculate tax rate
            pretax = field_data["pretaxIncome"].get(key)
            tax_exp = field_data["incomeTaxExpense"].get(key)
            effective_tax_rate = self._calculate_effective_tax_rate(pretax, tax_exp)
            
            item = {
                "period": p_info["period"],
                "fiscalYear": p_info["fiscalYear"],
                "fiscalQuarter": p_info["fiscalQuarter"],
                "currency": "IDR",
                "auditStatus": "UNAUDITED",
                "revenue": field_data["revenue"].get(key),
                "revenueGrowthYoY": revenue_growth_yoy,
                "cogs": field_data["cogs"].get(key),
                "grossProfit": field_data["grossProfit"].get(key),
                "operatingExpenses": field_data["operatingExpenses"].get(key),
                "sellingExpenses": None,
                "generalAdminExpenses": field_data["generalAdminExpenses"].get(key),
                "rdExpenses": None,
                "depreciationAmort": None,
                "ebit": None,
                "ebitda": field_data["ebitda"].get(key),
                "operatingIncome": None,
                "interestExpense": field_data["interestExpense"].get(key),
                "interestIncome": field_data["interestIncome"].get(key),
                "otherNonOperatingIncome": field_data["otherNonOperatingIncome"].get(key),
                "pretaxIncome": pretax,
                "incomeTaxExpense": tax_exp,
                "effectiveTaxRate": effective_tax_rate,
                "netIncome": field_data["netIncome"].get(key),
                "netIncomeAttributable": field_data["netIncome"].get(key),
                "minorityInterest": field_data["minorityInterest"].get(key),
                "eps": field_data["eps"].get(key),
                "epsDiluted": None,
                "sharesWeightedAvg": field_data["sharesWeightedAvg"].get(key),
            }
            
            result_data.append(item)
        
        return result_data


# Helper function untuk API
def scrape_stockbit_income_statement(symbol: str, headless: bool = False) -> Dict:
    """
    Helper function untuk scrape income statement dari Stockbit
    Usage: result = scrape_stockbit_income_statement("BBCA")
    """
    scraper = StockbitIncomeStatementScraper(symbol, headless=headless)
    return scraper.scrape()