import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from abc import ABC, abstractmethod
import time
import random

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from .config import (
    BROWSER_EXECUTABLES,
    URL_TEMPLATE,
    REPORT_TYPE_SELECTOR,
    DATA_TABLE_SELECTOR,
    FINANCIAL_WRAPPER,
)


class BaseStockbitScraper(ABC):
    """Base class untuk semua scraper Stockbit"""

    PAGE_SETTLE_MS = 400
    POST_SELECT_SETTLE_MS = 700
    POST_LOGIN_RESUME_SETTLE_MS = 1000
    SCROLL_SETTLE_RANGE = (0.2, 0.5)
    BLOCKED_RESOURCE_TYPES = {"media"}
    
    def __init__(self, symbol: str, report_type: str, headless: bool = False):
        self.symbol = str(symbol).strip().upper()
        self.report_type = report_type
        self.headless = headless
        self.profile_dir = Path("playwright_user_data")
        self.profile_dir.mkdir(exist_ok=True)
        self.context = None
        self.page = None
        
        if not self.symbol:
            raise ValueError("Symbol is required")
    
    def _find_browser_executable(self) -> Optional[str]:
        """Cari browser executable yang tersedia"""
        for executable in BROWSER_EXECUTABLES:
            if executable.exists():
                return str(executable)
        return None
    
    def _parse_numeric(self, raw_value: Optional[str]) -> Optional[Union[int, float]]:
        """Parse nilai numerik dari atribut data-value-idr"""
        if raw_value is None:
            return None
        raw_text = str(raw_value).strip()
        if not raw_text or raw_text.lower() in {"-", "—", "n/a", "nan"}:
            return None
        try:
            val = float(raw_text)
            return int(val) if val.is_integer() else val
        except ValueError:
            return None
    
    def _parse_period_label(self, label: str) -> Optional[Dict]:
        """Parse period label (contoh: Q126 -> Q1, 2026)"""
        match = re.match(r"(Q[1-4])(\d{2})", label)
        if match:
            period = match.group(1).upper()
            year_short = match.group(2)
            year = 2000 + int(year_short)
            quarter = int(period[1])
            return {
                "period": period,
                "fiscalYear": year,
                "fiscalQuarter": quarter,
                "key": f"{period}_{year}"
            }
        return None
    
    def launch_browser(self):
        """Launch browser dengan konfigurasi stealth"""
        playwright = sync_playwright().start()
        executable_path = self._find_browser_executable()
        
        context_args = {
            "user_data_dir": str(self.profile_dir),
            "headless": self.headless,
            "args": [
                "--start-maximized",
                "--window-size=1920,1080",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
            "ignore_default_args": ["--enable-automation"],
            "no_viewport": True,
        }
        
        if executable_path:
            context_args["executable_path"] = executable_path
        
        self.context = playwright.chromium.launch_persistent_context(**context_args)
        self._setup_resource_blocking()
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        
        # Inject stealth scripts
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['id-ID', 'id', 'en-US', 'en']
            });
            window.chrome = { runtime: {} };
        """)

    def _setup_resource_blocking(self):
        """Skip heavy resources that don't affect selector-based scraping."""
        if not self.context:
            return

        def _route_handler(route):
            try:
                if route.request.resource_type in self.BLOCKED_RESOURCE_TYPES:
                    route.abort()
                    return
            except Exception:
                pass
            route.continue_()

        self.context.route("**/*", _route_handler)
    
    def close_browser(self):
        """Close browser"""
        if self.context:
            self.context.close()
    
    def navigate_to_symbol(self, symbol: str = None):
        """Navigate ke halaman financial symbol"""
        if symbol:
            self.symbol = symbol
        url = URL_TEMPLATE.format(symbol=self.symbol)
        
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except PlaywrightTimeoutError:
            pass  # Continue anyway
    
    def select_report_type(self, report_type: str = None):
        """Pilih jenis laporan (Income Statement, Balance Sheet, Cash Flow)"""
        report_type = report_type or self.report_type
        
        try:
            self.page.wait_for_selector(REPORT_TYPE_SELECTOR, timeout=15000)
            self.page.select_option(REPORT_TYPE_SELECTOR, report_type)
            self.page.wait_for_timeout(self.POST_SELECT_SETTLE_MS)
        except PlaywrightTimeoutError:
            raise ValueError(f"Report type selector not found for {report_type}")
    
    def wait_for_table_load(self, timeout: int = 30000):
        """Tunggu tabel data load"""
        try:
            self.page.wait_for_selector(
                f"{DATA_TABLE_SELECTOR} tbody tr td[data-value-idr]",
                timeout=timeout,
                state="attached"
            )
        except PlaywrightTimeoutError:
            raise ValueError("Data table did not load")
    
    def scroll_to_table(self):
        """Scroll ke tabel untuk trigger lazy loading"""
        self.page.evaluate("""
            () => {
                const table = document.querySelector('#data_table_1');
                if (table) table.scrollIntoView({ behavior: 'auto', block: 'center' });
            }
        """)
        time.sleep(random.uniform(*self.SCROLL_SETTLE_RANGE))
    
    def extract_periods_from_header(self) -> List[Dict]:
        """Extract semua periode dari header tabel"""
        headers = self.page.locator(f"{DATA_TABLE_SELECTOR} thead th[data-label]").all()
        periods = []
        
        for i, th in enumerate(headers):
            label = th.get_attribute("data-label")
            if not label:
                continue
            
            period_info = self._parse_period_label(label)
            if period_info:
                period_info["index"] = i
                period_info["label"] = label
                periods.append(period_info)
        
        return periods
    
    def extract_all_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Extract semua data dari SEMUA tabel di halaman menggunakan JavaScript
        (termasuk tabel rasio yang berisi EPS, EBITDA, Share Outstanding)
        Returns: {periodKeys: [...], result: {field_name: [values...]}}
        """
        js_script = """
        () => {
            // 1. Ambil period keys dari tabel utama (#data_table_1)
            const mainTable = document.querySelector('#data_table_1');
            let periodKeys = [];
            if (mainTable) {
                const headers = Array.from(mainTable.querySelectorAll('thead th[data-label]'));
                periodKeys = headers.map(th => th.getAttribute('data-label'));
            }
            
            // 2. Search SEMUA tabel di halaman (penting buat nangkep EPS, EBITDA, dll)
            const allTables = document.querySelectorAll('table');
            const result = {};
            
            allTables.forEach(table => {
                const rows = table.querySelectorAll('tbody tr');
                rows.forEach(row => {
                    // Cari span dengan data-lang-1-full (nama lengkap) atau data-lang-1
                    let span = row.querySelector('span[data-lang-1-full]') || 
                            row.querySelector('span[data-lang-1]');
                    
                    if (span) {
                        let fieldName = span.getAttribute('data-lang-1-full') || 
                                    span.getAttribute('data-lang-1');
                        
                        // Skip kalau fieldName kosong
                        if (!fieldName || fieldName.trim() === '') return;
                        
                        const tds = row.querySelectorAll('td[data-value-idr]');
                        // Simpan hanya kalau belum ada (prioritas tabel pertama yang ketemu)
                        if (tds.length > 0 && !result[fieldName]) {
                            result[fieldName] = Array.from(tds).map(td => 
                                td.getAttribute('data-value-idr')
                            );
                        }
                    }
                });
            });
            
            return { periodKeys, result };
        }
        """
        
        raw_data = self.page.evaluate(js_script)
        if not raw_data:
            raise ValueError("Failed to extract data via JavaScript")
        
        return raw_data
    
    @abstractmethod
    def scrape(self) -> Dict:
        """Abstract method - harus diimplementasi di child class"""
        pass
    
    def _calculate_revenue_growth_yoy(
        self, 
        current_revenue: Optional[float], 
        prev_revenue: Optional[float]
    ) -> Optional[float]:
        """Hitung revenue growth YoY"""
        if current_revenue is not None and prev_revenue is not None and prev_revenue != 0:
            return round(((current_revenue - prev_revenue) / abs(prev_revenue)) * 100, 2)
        return None
    
    def _calculate_effective_tax_rate(
        self,
        pretax_income: Optional[float],
        tax_expense: Optional[float]
    ) -> Optional[float]:
        """Hitung effective tax rate"""
        if pretax_income is not None and pretax_income != 0 and tax_expense is not None:
            return round((abs(tax_expense) / abs(pretax_income)) * 100, 2)
        return None

