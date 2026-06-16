import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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

ROW_SELECTORS = {
    "revenue": "Total Revenue",
    "cogs": "Total Cost Of Goods Sold",
    "grossProfit": "Gross Profit",
    "operatingExpenses": "Total Operating Expense",
    "generalAdminExpenses": "General And Administrative Expense",
    "interestExpense": "Interest Expense",
    "interestIncome": "Interest Income",
    "otherNonOperatingIncome": "Non-Operating Income/Expense",
    "pretaxIncome": "Income Before Tax",
    "incomeTaxExpense": "Tax Expense",
    "netIncome": "Owners Of The Company",
    "minorityInterest": "Non-Controlling Interests",
    "eps": "EPS (Quarter)",
    "sharesWeightedAvg": "Share Outstanding",
    "ebitda": "EBITDA (Quarter)",
}

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

            # === STEP 1: LAUNCH BROWSER (Setup asli lu, gak gw ubah) ===
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

            # === STEP 2: NAVIGATE KE HALAMAN ===
            print(f"[2/6] Navigating to {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                print("   DOM loaded, waiting for network idle...")
                page.wait_for_load_state("networkidle", timeout=30000)
            except PlaywrightTimeoutError:
                print("   Network idle timeout, continuing anyway...")

            debug_dir = profile_dir / "debug"
            debug_dir.mkdir(exist_ok=True)
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            page.screenshot(path=str(debug_dir / f"{symbol}-after-nav-{ts}.png"))
            print(f"   Screenshot saved: {debug_dir / f'{symbol}-after-nav-{ts}.png'}")

            # === STEP 3: PILIH INCOME STATEMENT + SCROLL ===
            print(f"[3/6] Selecting Income Statement...")
            try:
                page.wait_for_selector(REPORT_TYPE_SELECTOR, timeout=15000)
                print("   Dropdown found!")

                # Pilih option value="1" (Income Statement)
                page.select_option(REPORT_TYPE_SELECTOR, "1")
                print("   Selected 'Income Statement'")

                # Tunggu network idle setelah pilih option (biar AJAX request selesai)
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except PlaywrightTimeoutError:
                    print("   Network idle timeout after select, continuing...")

                # Scroll sedikit ke bawah biar keliatan behaviour bot lagi scraping
                page.evaluate("window.scrollBy(0, 400);")
                print("   Scrolled down to show table...")

            except PlaywrightTimeoutError:
                print("   ERROR: Dropdown tidak ditemukan!")
                raise ValueError("Report type dropdown not found")

            # === STEP 4: TUNGGU TABEL MUNCUL (FIXED) ===
            print(f"[4/6] Waiting for data table to load...")
            try:
                # Tunggu wrapper tabel muncul sesuai tag HTML yang lu kasih
                page.wait_for_selector(
                    'div[data-cy="financial-table"]',
                    timeout=15000,
                    state="visible"
                )
                
                # Tunggu sampai row "Total Revenue" muncul. 
                # Ini foolproof buat mastiin data Income Statement bener-bener udah ke-render
                page.wait_for_selector(
                    'span[data-lang-1="Total Revenue"]',
                    timeout=15000,
                    state="visible"
                )
                print("   Table rows detected!")
            except PlaywrightTimeoutError:
                print("   ERROR: Table tidak muncul!")
                page.screenshot(path=str(debug_dir / f"{symbol}-no-table-{ts}.png"))
                raise ValueError("Data table did not load")

            # === STEP 5: EKSTRAK DATA ===
            print(f"[5/6] Extracting data...")

            # Ambil semua periode dari header
            headers = page.locator(f"{DATA_TABLE_SELECTOR} thead th[data-label]").all()
            periods_info = []
            for i, th in enumerate(headers):
                label = th.get_attribute("data-label")  # contoh: "Q126"
                text = th.inner_text().strip()  # contoh: "Q1 2026"

                if not label:
                    continue

                match = re.search(r"(Q[1-4])\s*(\d{4})", text, re.IGNORECASE)
                if match:
                    period = match.group(1).upper()
                    year = int(match.group(2))
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

            if not periods_info:
                raise ValueError("No periods found in table header")

            # Ambil data untuk setiap field
            field_data = {field: {} for field in ROW_SELECTORS}

            for field, row_name in ROW_SELECTORS.items():
                # Cari row dengan data-lang-1
                xpath = f"//tr[.//span[@data-lang-1='{row_name}']]"
                row = page.locator(xpath).first

                if row.count() == 0:
                    print(f"   WARNING: Row '{row_name}' not found")
                    continue

                tds = row.locator("td[data-raw]").all()

                for p_info in periods_info:
                    idx = p_info["index"]
                    if idx < len(tds):
                        raw_val = tds[idx].get_attribute("data-raw")
                        field_data[field][p_info["key"]] = _parse_numeric(raw_val)
                    else:
                        field_data[field][p_info["key"]] = None

            # === STEP 6: SUSUN HASIL ===
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