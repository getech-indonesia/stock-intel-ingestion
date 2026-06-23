import logging
from typing import Any, Dict, List, Optional, Union
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .base_scraper import BaseStockbitScraper
from .stockbit_session import StockbitSessionHandler
from .config import BALANCE_SHEET_FIELDS, DATA_TABLE_SELECTOR, FINANCIAL_WRAPPER


logger = logging.getLogger(__name__)


class StockbitBalanceSheetScraper(BaseStockbitScraper):
    """Scraper untuk Balance Sheet"""
    
    MAX_SESSION_RECOVERY_ATTEMPTS = 2

    def __init__(self, symbol: str, headless: bool = False):
        super().__init__(symbol, report_type="2", headless=headless)
        self.field_mapping = BALANCE_SHEET_FIELDS
        self.session_handler = None
    
    def scrape(self) -> Dict:
        """Main scraping method untuk Balance Sheet"""
        try:
            # Launch browser
            print(f"[1/7] Launching browser...")
            self.launch_browser()
            self.session_handler = StockbitSessionHandler(self.page)
            return self._scrape_with_session_retry()
            
        except PlaywrightTimeoutError as exc:
            raise ValueError(f"Timeout: {exc}") from exc
        except Exception as exc:
            raise ValueError(f"Failed: {exc}") from exc
        finally:
            self.close_browser()

    def _scrape_with_session_retry(self) -> Dict:
        """Run the scrape and recover once if Stockbit asks for a fresh login."""
        for attempt in range(1, self.MAX_SESSION_RECOVERY_ATTEMPTS + 1):
            try:
                return self._scrape_once()
            except ValueError as exc:
                if not self._is_session_recovery_error(exc) or attempt >= self.MAX_SESSION_RECOVERY_ATTEMPTS:
                    raise

                print("\n[LOGIN] Session Stockbit habis. Tunggu login ulang, lalu lanjut request emiten yang sempat berhenti...")
                if not self._wait_for_login_and_resume():
                    raise ValueError("Session expired dan user tidak login") from exc

        raise ValueError("Failed to recover Stockbit session")

    def _scrape_once(self) -> Dict:
        """Scrape sekali jalan untuk satu simbol."""
        # Navigate
        print(f"[2/7] Navigating to {self.symbol}...")
        self.navigate_to_symbol()

        # Kalau Stockbit lempar ke login page, tahan dulu untuk login manual
        if self.session_handler.is_login_page() or self.session_handler.check_session_expired():
            if not self._wait_for_login_and_resume():
                raise ValueError("Session expired dan user tidak login")

        # Select Balance Sheet
        print(f"[3/7] Selecting Balance Sheet...")
        self.select_report_type("2")

        # Kalau setelah select masih di login page, retry lagi setelah manual login
        if self.session_handler.is_login_page() or self.session_handler.check_session_expired():
            if not self._wait_for_login_and_resume():
                raise ValueError("Session expired setelah select balance sheet")

        # Wait for table
        print(f"[4/7] Waiting for data table...")
        try:
            self.page.locator(FINANCIAL_WRAPPER).wait_for(state="visible", timeout=30000)
            self.page.wait_for_timeout(1000)
        except PlaywrightTimeoutError:
            if self.session_handler.is_login_page() or self.session_handler.check_session_expired():
                raise ValueError("Session expired saat menunggu data table balance sheet")
            raise ValueError("Data table balance sheet tidak terdeteksi")
        print("   Table wrapper detected!")
        
        # Scroll to table
        self.scroll_to_table()
        
        # Extract data
        print(f"[5/7] Extracting data...")
        raw_extracted = self._extract_balance_sheet_data()
        raw_data = raw_extracted.get("result", {})
        currency = raw_extracted.get("currency", "IDR")
        
        periods = self.extract_periods_from_header()
        print(f"   Found {len(periods)} periods: {[p['key'] for p in periods[:5]]}...")
        if not periods:
            print(f"[WARN] Balance sheet period headers are empty for symbol {self.symbol}", flush=True)
            logger.warning("Balance sheet period headers are empty for symbol %s", self.symbol)
        
        # Build result
        print(f"[6/7] Building result...")
        result_data = self._build_result(raw_data, periods, currency)
        if not result_data:
            print(f"[WARN] Balance sheet scrape produced empty data for symbol {self.symbol}", flush=True)
            logger.warning("Balance sheet scrape produced empty data for symbol %s", self.symbol)
        
        print(f"[7/7] Done! Extracted {len(result_data)} periods")
        
        return {
            "status": "ok",
            "symbol": self.symbol,
            "data": result_data
        }

    def _wait_for_login_and_resume(self) -> bool:
        """Tunggu login manual lalu kembali ke simbol yang sedang diproses."""
        if not self.session_handler.wait_for_manual_login(timeout=300):
            return False

        print(f"   Resuming: Navigating back to {self.symbol}...")
        self.navigate_to_symbol()
        self.page.wait_for_timeout(self.POST_LOGIN_RESUME_SETTLE_MS)
        self.select_report_type("2")
        return True

    @staticmethod
    def _is_session_recovery_error(exc: Exception) -> bool:
        message = str(exc).lower()
        if "user tidak login" in message:
            return False
        return any(
            marker in message
            for marker in (
                "session expired",
                "login",
                "manual login",
                "stockbit minta login",
            )
        )

    def _extract_balance_sheet_data(self) -> Dict[str, Any]:
        """Custom extractor to capture data-value-idr and section tracking"""
        js_script = """
        () => {
            const result = {};
            const allTables = document.querySelectorAll('table');
            let currentSection = "";
            
            allTables.forEach(table => {
                const rows = table.querySelectorAll('tbody tr');
                rows.forEach(row => {
                    let span = row.querySelector('span[data-lang-1-full]') || 
                               row.querySelector('span[data-lang-1]');
                    
                    let idName = "";
                    let enName = "";
                    if (span) {
                        idName = span.getAttribute('data-lang-0-full') || span.getAttribute('data-lang-0') || "";
                        enName = span.getAttribute('data-lang-1-full') || span.getAttribute('data-lang-1') || "";
                    }
                    
                    let tdFirst = row.querySelector('td');
                    let rowText = tdFirst ? tdFirst.innerText.trim() : "";
                    
                    // Track sections
                    if (enName === "Assets") currentSection = "assets";
                    else if (enName === "Current Assets") currentSection = "current_assets";
                    else if (enName === "Non-Current Assets") currentSection = "non_current_assets";
                    else if (enName === "Current Liabilities") currentSection = "current_liabilities";
                    else if (enName === "Non-Current Liabilities") currentSection = "non_current_liabilities";
                    else if (enName === "Equity") currentSection = "equity";
                    
                    const tds = row.querySelectorAll('td[data-value-idr]');
                    if (tds.length === 0) return;
                    
                    const values = Array.from(tds).map(td => td.getAttribute('data-value-idr'));
                    
                    const isTotalRow = row.classList.contains('total') || rowText.toLowerCase().startsWith('total ');
                    
                    const addResult = (key, isTotal) => {
                        if (!key) return;
                        key = key.trim();
                        if (!result[key] || isTotal) {
                            result[key] = values;
                        }
                    };
                    
                    // Map special Others rows based on current section
                    if (rowText.toLowerCase() === "others") {
                        if (currentSection === "current_assets") {
                            addResult("Others_Current_Assets", true);
                        } else if (currentSection === "non_current_assets") {
                            addResult("Others_Non_Current_Assets", true);
                        } else if (currentSection === "equity") {
                            addResult("Others_Equity", true);
                        }
                    } else {
                        if (idName) addResult("ID:" + idName, isTotalRow);
                        if (enName) addResult("EN:" + enName, isTotalRow);
                        if (rowText) addResult("TEXT:" + rowText, isTotalRow);
                    }
                });
            });
            
            let currency = "IDR";
            const currencyInput = document.querySelector('input[name="selected_currency"]');
            if (currencyInput && currencyInput.value) {
                currency = currencyInput.value.toUpperCase();
            }
            
            return { result, currency };
        }
        """
        raw_data = self.page.evaluate(js_script)
        if not raw_data:
            raise ValueError("Failed to extract data via JavaScript")
        if not raw_data.get("result"):
            print(f"[WARN] Balance sheet raw extraction returned empty result for symbol {self.symbol}", flush=True)
            logger.warning("Balance sheet raw extraction returned empty result for symbol %s", self.symbol)
        return raw_data

    def _get_row_value(self, raw_data: Dict, id_key: str = None, en_key: str = None, text_key: str = None) -> List[Any]:
        """Retrieve values from JavaScript-extracted dictionary"""
        if id_key and f"ID:{id_key}" in raw_data:
            return raw_data[f"ID:{id_key}"]
        if en_key and f"EN:{en_key}" in raw_data:
            return raw_data[f"EN:{en_key}"]
        if text_key and f"TEXT:{text_key}" in raw_data:
            return raw_data[f"TEXT:{text_key}"]
        if text_key and text_key in raw_data:
            return raw_data[text_key]
        return []

    def _get_value_at_index(self, values: List[Any], index: int) -> Optional[Union[int, float]]:
        """Retrieve and parse numeric value at a specific column index"""
        if index < len(values):
            return self._parse_numeric(values[index])
        return None

    def _safe_subtract(self, total: Optional[Union[int, float]], *parts: Optional[Union[int, float]]) -> Optional[Union[int, float]]:
        """Calculate subtraction safely with optional/None values"""
        if total is None:
            return None
        res = total
        for part in parts:
            if part is not None:
                res -= part
        return res

    def _build_result(self, raw_data: Dict, periods: List[Dict], currency: str) -> List[Dict]:
        """Build results for each period"""
        # Fetch all rows first
        cash_list = self._get_row_value(raw_data, id_key="Aset", en_key="Assets")
        receivables_list = self._get_row_value(raw_data, id_key="Piutang Usaha", en_key="Trade Receivables")
        inventory_list = self._get_row_value(raw_data, id_key="Persediaan", en_key="Inventories")
        total_curr_assets_list = self._get_row_value(raw_data, id_key="Aset Lancar", en_key="Current Assets")
        
        ppe_list = self._get_row_value(raw_data, id_key="Aset Tetap", en_key="Property, Plant And Equipment")
        intangible_list = self._get_row_value(raw_data, id_key="Aset Tak Berwujud", en_key="Intangible Assets")
        goodwill_list = self._get_row_value(raw_data, id_key="Goodwill", en_key="Goodwill")
        total_non_curr_assets_list = self._get_row_value(raw_data, id_key="Aset Tidak Lancar", en_key="Non-Current Assets")
        total_assets_list = self._get_row_value(raw_data, id_key="Aset", en_key="Assets")
        
        short_term_debt_list = self._get_row_value(raw_data, id_key="Bagian Lancar Atas Liabilitas Jangka Panjang", en_key="Current Portion Of Long-Term Debt")
        accounts_payable_list = self._get_row_value(raw_data, id_key="Utang Usaha", en_key="Trade Payables")
        total_curr_liab_list = self._get_row_value(raw_data, id_key="Liabilitas Jangka Pendek", en_key="Current Liabilities")
        
        long_term_debt_list = self._get_row_value(raw_data, id_key="Liabilitas Jangka Panjang", en_key="Non-Current Liabilities")
        deferred_tax_liab_list = self._get_row_value(raw_data, id_key="Liabilitas Pajak Tangguhan", en_key="Deferred Tax Liabilities")
        total_non_curr_liab_list = self._get_row_value(raw_data, id_key="Liabilitas Jangka Panjang", en_key="Non-Current Liabilities")
        total_liabilities_list = self._get_row_value(raw_data, id_key="Liabilitas", en_key="Liabilities")
        
        common_stock_list = self._get_row_value(raw_data, id_key="Modal Saham", en_key="Capital Stock")
        apic_list = self._get_row_value(raw_data, id_key="Tambahan Modal Disetor", en_key="Additional Paid-Up Capital")
        retained_earnings_list = self._get_row_value(raw_data, id_key="Saldo Laba", en_key="Retained Earnings")
        other_equity_list = self._get_row_value(raw_data, text_key="Others_Equity")
        minority_interest_list = self._get_row_value(raw_data, id_key="Kepentingan Non Pengendali", en_key="Non-Controlling Interests")
        total_equity_list = self._get_row_value(raw_data, id_key="Ekuitas", en_key="Equity")
        
        bvps_list = self._get_row_value(raw_data, id_key="Book Value Per Share (Quarter)", en_key="Book Value Per Share (Quarter)")
        net_debt_list = self._get_row_value(raw_data, id_key="Net Debt (Quarter)", en_key="Net Debt (Quarter)")
        working_capital_list = self._get_row_value(raw_data, id_key="Working Capital (Quarter)", en_key="Working Capital (Quarter)")

        result_data = []
        for p_info in periods:
            idx = p_info["index"]
            
            cash = self._get_value_at_index(cash_list, idx)
            accounts_receivable = self._get_value_at_index(receivables_list, idx)
            inventory = self._get_value_at_index(inventory_list, idx)
            total_current_assets = self._get_value_at_index(total_curr_assets_list, idx)
            other_current_assets = self._safe_subtract(total_current_assets, cash, accounts_receivable, inventory)
            
            property_plant_equipment = self._get_value_at_index(ppe_list, idx)
            intangible_assets = self._get_value_at_index(intangible_list, idx)
            goodwill = self._get_value_at_index(goodwill_list, idx)
            total_non_current_assets = self._get_value_at_index(total_non_curr_assets_list, idx)
            other_non_current_assets = self._safe_subtract(total_non_current_assets, property_plant_equipment, intangible_assets, goodwill)
            total_assets = self._get_value_at_index(total_assets_list, idx)
            
            short_term_debt = self._get_value_at_index(short_term_debt_list, idx)
            accounts_payable = self._get_value_at_index(accounts_payable_list, idx)
            total_current_liabilities = self._get_value_at_index(total_curr_liab_list, idx)
            other_current_liabilities = self._safe_subtract(total_current_liabilities, short_term_debt, accounts_payable)
            
            long_term_debt = self._get_value_at_index(long_term_debt_list, idx)
            deferred_tax_liabilities = self._get_value_at_index(deferred_tax_liab_list, idx)
            total_non_current_liabilities = self._get_value_at_index(total_non_curr_liab_list, idx)
            other_non_current_liabilities = self._safe_subtract(total_non_current_liabilities, long_term_debt, deferred_tax_liabilities)
            total_liabilities = self._get_value_at_index(total_liabilities_list, idx)
            
            common_stock = self._get_value_at_index(common_stock_list, idx)
            additional_paid_in_capital = self._get_value_at_index(apic_list, idx)
            retained_earnings = self._get_value_at_index(retained_earnings_list, idx)
            other_equity = self._get_value_at_index(other_equity_list, idx)
            minority_interest_equity = self._get_value_at_index(minority_interest_list, idx)
            total_equity = self._get_value_at_index(total_equity_list, idx)
            
            book_value_per_share = self._get_value_at_index(bvps_list, idx)
            net_debt = self._get_value_at_index(net_debt_list, idx)
            working_capital = self._get_value_at_index(working_capital_list, idx)
            
            item = {
                "period": p_info["period"],
                "fiscalYear": p_info["fiscalYear"],
                "fiscalQuarter": p_info["fiscalQuarter"],
                "currency": currency,
                "auditStatus": "UNAUDITED",
                
                "cash": cash,
                "shortTermInvestments": None,
                "accountsReceivable": accounts_receivable,
                "inventory": inventory,
                "otherCurrentAssets": other_current_assets,
                "totalCurrentAssets": total_current_assets,
                
                "propertyPlantEquipment": property_plant_equipment,
                "intangibleAssets": intangible_assets,
                "goodwill": goodwill,
                "longTermInvestments": None,
                "otherNonCurrentAssets": other_non_current_assets,
                "totalNonCurrentAssets": total_non_current_assets,
                "totalAssets": total_assets,
                
                "shortTermDebt": short_term_debt,
                "accountsPayable": accounts_payable,
                "deferredRevenue": None,
                "otherCurrentLiabilities": other_current_liabilities,
                "totalCurrentLiabilities": total_current_liabilities,
                
                "longTermDebt": long_term_debt,
                "deferredTaxLiabilities": deferred_tax_liabilities,
                "otherNonCurrentLiabilities": other_non_current_liabilities,
                "totalNonCurrentLiabilities": total_non_current_liabilities,
                "totalLiabilities": total_liabilities,
                
                "commonStock": common_stock,
                "additionalPaidInCapital": additional_paid_in_capital,
                "retainedEarnings": retained_earnings,
                "treasuryStock": None,
                "otherEquity": other_equity,
                "minorityInterestEquity": minority_interest_equity,
                "totalEquity": total_equity,
                
                "bookValuePerShare": book_value_per_share,
                "netDebt": net_debt,
                "workingCapital": working_capital
            }
            result_data.append(item)
            
        return result_data


def scrape_balance_sheet(symbol: str, headless: bool = False) -> Dict:
    """
    Helper function untuk scrape balance sheet dari Stockbit
    Usage: result = scrape_balance_sheet("BBCA")
    """
    scraper = StockbitBalanceSheetScraper(symbol, headless=headless)
    return scraper.scrape()

