import re
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

URL_TEMPLATE = "https://stockbit.com/symbol/{symbol}/financials"
REPORT_TYPE_SELECTOR = 'select[data-cy="report-type"]'
DATA_TABLE_SELECTOR = "#data_table_1"

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

            print(f"[1/6] Launching browser (Stealth Mode)...")
            executable_path = _find_browser_executable()

            # Argument Stealth untuk mencegah deteksi bot
            args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-extensions",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1920,1080",
                "--lang=id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            ]

            context_args = {
                "user_data_dir": str(profile_dir),
                "headless": False,
                "args": args,
                "ignore_default_args": ["--enable-automation"],
                "viewport": {"width": 1920, "height": 1080},
                "locale": "id-ID",
                "timezone_id": "Asia/Jakarta",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            }

            if executable_path:
                print(f"   Using: {executable_path}")
                context_args["executable_path"] = executable_path

            context = playwright.chromium.launch_persistent_context(**context_args)
            page = context.pages[0] if context.pages else context.new_page()

            # INJECT STEALTH SCRIPTS: Menghapus jejak webdriver dari navigator
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['id-ID', 'id', 'en-US', 'en']
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                window.chrome = {
                    runtime: {}
                };
            """)

            print(f"[2/6] Navigating to {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                print("   DOM loaded, waiting for network idle...")
                page.wait_for_load_state("networkidle", timeout=30000)
            except PlaywrightTimeoutError:
                print("   Network idle timeout, continuing anyway...")

            # Delay acak menyerupai manusia membaca halaman
            time.sleep(random.uniform(1.5, 3.0))

            print(f"[3/6] Selecting Income Statement...")
            try:
                page.wait_for_selector(REPORT_TYPE_SELECTOR, timeout=15000)
                print("   Dropdown found!")
                
                # Simulasi gerakan mouse ke arah dropdown sebelum interaksi
                dropdown = page.locator(REPORT_TYPE_SELECTOR)
                box = dropdown.bounding_box()
                if box:
                    page.mouse.move(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                    time.sleep(random.uniform(0.5, 1.0))
                
                page.select_option(REPORT_TYPE_SELECTOR, "1")
                print("   Selected 'Income Statement'")
            except PlaywrightTimeoutError:
                print("   ERROR: Dropdown tidak ditemukan!")
                raise ValueError("Report type dropdown not found")

            print(f"[4/6] Waiting for data table to load...")
            try:
                page.wait_for_selector(
                    f"{DATA_TABLE_SELECTOR} tbody tr td[data-raw]",
                    timeout=30000,
                    state="attached"
                )
                print("   Table data detected in DOM!")
            except PlaywrightTimeoutError:
                print("   ERROR: Table tidak muncul!")
                raise ValueError("Data table did not load")

            # Simulasi scrolling manusia (naik turun acak)
            print("   Scrolling like a human...")
            for _ in range(3):
                scroll_y = random.randint(300, 600)
                page.evaluate(f"window.scrollBy(0, {scroll_y});")
                time.sleep(random.uniform(0.8, 1.5))
            
            # Kembali fokus ke tabel
            page.evaluate("""
                () => {
                    const table = document.querySelector('#data_table_1');
                    if (table) table.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            """)
            time.sleep(random.uniform(1.0, 2.0))

            print(f"[5/6] Extracting data via JavaScript...")
            
            js_script = """
            () => {
                const mainTable = document.querySelector('#data_table_1');
                let periodKeys = [];
                if (mainTable) {
                    const headers = Array.from(mainTable.querySelectorAll('thead th[data-label]'));
                    periodKeys = headers.map(th => th.getAttribute('data-label'));
                }
                
                const allTables = document.querySelectorAll('table');
                const result = {};
                
                allTables.forEach(table => {
                    const rows = table.querySelectorAll('tbody tr');
                    rows.forEach(row => {
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
                "Owners Of The Company": "netIncome",
                "Non-Controlling Interests": "minorityInterest",
                "EPS (Quarter)": "eps",
                "Share Outstanding": "sharesWeightedAvg",
                "EBITDA (Quarter)": "ebitda",
            }

            field_data = {v: {} for v in FIELD_MAP.values()}

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

                prev_year = p_info["fiscalYear"] - 1
                prev_key = f"{p_info['period']}_{prev_year}"

                current_rev = field_data["revenue"].get(key)
                prev_rev = field_data["revenue"].get(prev_key)

                revenue_growth_yoy = None
                if current_rev is not None and prev_rev is not None and prev_rev != 0:
                    revenue_growth_yoy = round(((current_rev - prev_rev) / abs(prev_rev)) * 100, 2)

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
            
            # Delay sebelum tutup browser agar tidak mencurigakan (seperti user yang masih membaca)
            time.sleep(random.uniform(2.0, 4.0))
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