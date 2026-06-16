import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

URL_TEMPLATE = "https://stockbit.com/symbol/{symbol}/financials"
REPORT_TYPE_SELECTOR = 'select[data-cy="report-type"]'

CHROME_EXECUTABLES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
]
BRAVE_EXECUTABLES = [
    Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
    Path(r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"),
]
BROWSER_EXECUTABLES = CHROME_EXECUTABLES + BRAVE_EXECUTABLES

def _find_browser_executable() -> Optional[str]:
    for executable in BROWSER_EXECUTABLES:
        if executable.exists():
            return str(executable)
    return None

def _parse_numeric(raw_value: Optional[str]) -> Optional[Union[int, float]]:
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

def scrape_stockbit_income_statement(symbol: str) -> dict:
    symbol = str(symbol).strip().upper()
    if not symbol:
        raise ValueError("Symbol is required")

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    except ImportError as exc:
        raise ImportError(
            "Playwright is required. Install with `pip install playwright` then `playwright install`."
        ) from exc

    url = URL_TEMPLATE.format(symbol=symbol)

    try:
        with sync_playwright() as playwright:
            profile_dir = Path("playwright_user_data")
            profile_dir.mkdir(exist_ok=True)

            print(f"[1/6] Launching browser...")
            executable_path = _find_browser_executable()

            if executable_path:
                print(f"   Using: {executable_path}")
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    executable_path=executable_path,
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"],
                )
            else:
                print("   Using default Chromium")
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"],
                )

            page = context.pages[0] if context.pages else context.new_page()

            print(f"[2/6] Navigating to {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                print("   DOM loaded, waiting for network idle...")
                page.wait_for_load_state("networkidle", timeout=30000)
            except PlaywrightTimeoutError:
                print("   Network idle timeout, continuing anyway...")

            print(f"[3/6] Selecting Income Statement...")
            try:
                page.wait_for_selector(REPORT_TYPE_SELECTOR, timeout=15000)
                print("   Dropdown found!")
                page.select_option(REPORT_TYPE_SELECTOR, "1")
                print("   Selected 'Income Statement'")
            except PlaywrightTimeoutError:
                print("   ERROR: Dropdown tidak ditemukan!")
                raise ValueError("Report type dropdown not found")

            print(f"[4/6] Waiting for data table to load...")
            try:
                page.wait_for_selector(
                    "#data_table_1 tbody tr td[data-raw]",
                    timeout=30000,
                    state="attached"
                )
                print("   Table data detected in DOM!")
            except PlaywrightTimeoutError:
                print("   ERROR: Table tidak muncul!")
                raise ValueError("Data table did not load")

            page.evaluate("""
                () => {
                    const table = document.querySelector('#data_table_1');
                    if (table) table.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            """)
            page.wait_for_timeout(1000)
            print("   Scrolled to table")

            print(f"[5/6] Extracting data via JavaScript...")
            
            # JavaScript yang search SEMUA tabel di halaman
            js_script = """
            () => {
                // Get period keys from main table
                const mainTable = document.querySelector('#data_table_1');
                let periodKeys = [];
                if (mainTable) {
                    const headers = Array.from(mainTable.querySelectorAll('thead th[data-label]'));
                    periodKeys = headers.map(th => th.getAttribute('data-label'));
                }
                
                // Search ALL tables on the page for data rows
                const allTables = document.querySelectorAll('table');
                const result = {};
                
                allTables.forEach(table => {
                    const rows = table.querySelectorAll('tbody tr');
                    rows.forEach(row => {
                        // Try data-lang-1-full first (complete name), fallback to data-lang-1
                        let span = row.querySelector('span[data-lang-1-full]') || row.querySelector('span[data-lang-1]');
                        if (span) {
                            let fieldName = span.getAttribute('data-lang-1-full') || span.getAttribute('data-lang-1');
                            const tds = row.querySelectorAll('td[data-raw]');
                            if (tds.length > 0 && !result[fieldName]) {
                                result[fieldName] = Array.from(tds).map(td => td.getAttribute('data-raw'));
                            }
                        }
                    });
                });
                
                return { periodKeys, result };
            }
            """
            
            raw_data = page.evaluate(js_script)
            if not raw_data:
                raise ValueError("Failed to extract data via JavaScript")

            period_keys = raw_data['periodKeys']
            row_data = raw_data['result']

            # Parse period keys
            periods_info = []
            for i, label in enumerate(period_keys):
                match = re.match(r"(Q[1-4])(\d{2})", label)
                if match:
                    period = match.group(1).upper()
                    year_short = match.group(2)
                    year = 2000 + int(year_short)
                    quarter = int(period[1])
                    periods_info.append({
                        "index": i,
                        "label": label,
                        "period": period,
                        "fiscalYear": year,
                        "fiscalQuarter": quarter,
                        "key": f"{period}_{year}"
                    })

            print(f"   Found {len(periods_info)} periods: {[p['key'] for p in periods_info[:5]]}...")

            # Mapping nama field dari HTML ke key JSON
            # FIX: Net Income sekarang ambil dari "Owners Of The Company"
            FIELD_MAP = {
                "Total Revenue": "revenue",
                "Total Cost Of Goods Sold": "cogs",
                "Gross Profit": "grossProfit",
                "Total Operating Expense": "operatingExpenses",
                "General And Administrative Expense": "generalAdminExpenses",
                "Interest Expense": "interestExpense",
                "Interest Income": "interestIncome",
                "Non-Operating Income/Expense": "otherNonOperatingIncome",
                "Income Before Tax": "pretaxIncome",
                "Tax Expense": "incomeTaxExpense",
                "Owners Of The Company": "netIncome",  # FIXED: dari "Net Income For The Period"
                "Non-Controlling Interests": "minorityInterest",
                "EPS (Quarter)": "eps",
                "Share Outstanding": "sharesWeightedAvg",
                "EBITDA (Quarter)": "ebitda",
            }

            field_data = {v: {} for v in FIELD_MAP.values()}

            # Debug: print semua field yang ditemukan
            print(f"   Fields found in HTML: {list(row_data.keys())}")

            # Masukkan data ke dalam dictionary
            for html_name, py_name in FIELD_MAP.items():
                if html_name in row_data:
                    values = row_data[html_name]
                    for i, val in enumerate(values):
                        if i < len(periods_info):
                            field_data[py_name][periods_info[i]["key"]] = _parse_numeric(val)
                else:
                    print(f"   WARNING: Row '{html_name}' not found")

            print(f"[6/6] Building result...")

            result_data = []
            for p_info in periods_info:
                key = p_info["key"]

                # Hitung Revenue Growth YoY
                prev_year = p_info["fiscalYear"] - 1
                prev_key = f"{p_info['period']}_{prev_year}"

                current_rev = field_data["revenue"].get(key)
                prev_rev = field_data["revenue"].get(prev_key)

                revenue_growth_yoy = None
                if current_rev is not None and prev_rev is not None and prev_rev != 0:
                    revenue_growth_yoy = round(((current_rev - prev_rev) / abs(prev_rev)) * 100, 2)

                # Hitung Effective Tax Rate
                pretax = field_data["pretaxIncome"].get(key)
                tax_exp = field_data["incomeTaxExpense"].get(key)
                effective_tax_rate = None
                if pretax is not None and pretax != 0 and tax_exp is not None:
                    effective_tax_rate = round((abs(tax_exp) / abs(pretax)) * 100, 2)

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

            print(f"   Done! Extracted {len(result_data)} periods")
            context.close()

            return {
                "status": "ok",
                "symbol": symbol,
                "data": result_data
            }

    except PlaywrightTimeoutError as exc:
        raise ValueError(f"Timeout: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Failed: {exc}") from exc