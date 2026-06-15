import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

URL_TEMPLATE = "https://stockbit.com/symbol/{symbol}/financials"
REPORT_TYPE_SELECTOR = 'select[data-cy="report-type"]'
PERIOD_HEADER_SELECTOR = "//table[@id='data_table_1']/thead/tr/th[2]"
DATA_TABLE_SELECTOR = "#data_table_1"

BRAVE_EXECUTABLES = [
    Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
    Path(r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"),
]

SELECTORS = {
    "revenue": "//span[@data-lang-0='Pemilik Entitas Induk']/ancestor::tr/td[2]",
    "cogs": "//span[@data-lang-0='Total Beban Pokok Penjualan']/ancestor::tr/td[2]",
    "grossProfit": "//span[@data-lang-0='Laba Kotor']/ancestor::tr/td[2]",
    "operatingExpenses": "//span[@data-lang-0='Total Beban Usaha']/ancestor::tr/td[2]",
    "generalAdminExpenses": "//span[@data-lang-0='Beban Umum Dan Administrasi']/ancestor::tr/td[2]",
    "interestExpense": "//span[@data-lang-0='Beban Bunga']/ancestor::tr/td[2]",
    "interestIncome": "//span[@data-lang-0='Pendapatan Bunga']/ancestor::tr/td[2]",
    "otherNonOperatingIncome": "//span[@data-lang-0='Penghasilan/Beban Lain-Lain']/ancestor::tr/td[2]",
    "pretaxIncome": "//span[@data-lang-0='Laba Sebelum Pajak']/ancestor::tr/td[2]",
    "incomeTaxExpense": "//span[@data-lang-0='Beban Pajak Penghasilan']/ancestor::tr/td[2]",
    "netIncome": "//span[@data-lang-0='Pemilik Entitas Induk']/ancestor::tr/td[2]",
    "netIncomeAttributable": "//span[@data-lang-0='Pemilik Entitas Induk']/ancestor::tr/td[2]",
    "minorityInterest": "//span[@data-lang-0='Kepentingan Non-Pegendali']/ancestor::tr/td[2]",
    "eps": "//span[@data-lang-0='EPS (Quarter)']/ancestor::tr/td[2]",
    "sharesWeightedAvg": "//span[@data-lang-0='Share Outstanding']/ancestor::tr/td[2]",
    "ebitda": "//span[@data-lang-0='EBITDA (Quarter)']/ancestor::tr/td[2]",
}

FISCAL_QUARTER_END = {
    "Q1": "03-31",
    "Q2": "06-30",
    "Q3": "09-30",
    "Q4": "12-31",
}


def _parse_numeric(raw_value: Optional[str]) -> Optional[Union[int, float]]:
    if raw_value is None:
        return None

    raw_text = str(raw_value).strip()
    if not raw_text:
        return None

    if raw_text in {"-", "—", "n/a", "N/A", "NaN"}:
        return None

    negative = raw_text.startswith("(") and raw_text.endswith(")")
    if negative:
        raw_text = raw_text[1:-1]

    raw_text = raw_text.replace("\xa0", "")
    raw_text = re.sub(r"[^0-9,\.\-]", "", raw_text)
    raw_text = raw_text.replace(" ", "")

    if not raw_text:
        return None

    if raw_text.count(",") and raw_text.count("."):
        raw_text = raw_text.replace(".", "").replace(",", ".")
    elif raw_text.count(",") == 1 and raw_text.count(".") == 0:
        integer_part, fractional_part = raw_text.split(",")
        if len(fractional_part) <= 2:
            raw_text = f"{integer_part}.{fractional_part}"
        else:
            raw_text = raw_text.replace(",", "")
    elif raw_text.count(".") > 1:
        raw_text = raw_text.replace(".", "")

    try:
        if "." in raw_text:
            value = float(raw_text)
            return int(value) if value.is_integer() else value
        return int(raw_text)
    except ValueError:
        return None


def _parse_period_header(header_text: Optional[str]) -> tuple[str, int, int]:
    if not header_text:
        raise ValueError("Report period header is missing")

    match = re.search(r"(Q[1-4])\s*(\d{4})", header_text, re.IGNORECASE)
    if not match:
        raise ValueError(f"Unable to parse report period from header '{header_text}'")

    period = match.group(1).upper()
    fiscal_year = int(match.group(2))
    fiscal_quarter = int(period[1])
    return period, fiscal_year, fiscal_quarter


def _period_end_date(period: str, year: int) -> str:
    if period not in FISCAL_QUARTER_END:
        raise ValueError(f"Unknown fiscal quarter '{period}'")
    return f"{year}-{FISCAL_QUARTER_END[period]}"


def _get_xpath_text(page: Any, xpath: str) -> Optional[str]:
    locator = page.locator(f"xpath={xpath}")
    if locator.count() == 0:
        return None

    text = locator.first.text_content()
    if text is None:
        return None
    return text.strip()


def _collect_values(page: Any) -> Dict[str, Optional[Union[int, float]]]:
    result: Dict[str, Optional[Union[int, float]]] = {}
    for key, xpath in SELECTORS.items():
        text = _get_xpath_text(page, xpath)
        result[key] = _parse_numeric(text)
    return result


def scrape_stockbit_income_statement(symbol: str) -> dict:
    symbol = str(symbol).strip().upper()
    if not symbol:
        raise ValueError("Symbol is required")

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    except ImportError as exc:
        raise ImportError(
            "Playwright is required for Stockbit scraping. Install it with `pip install playwright` "
            "and then run `playwright install`.") from exc

    url = URL_TEMPLATE.format(symbol=symbol)

    try:
        with sync_playwright() as playwright:
            executable_path = None
            for brave_path in BRAVE_EXECUTABLES:
                if brave_path.exists():
                    executable_path = str(brave_path)
                    break

            if executable_path:
                browser = playwright.chromium.launch(
                    headless=False,
                    executable_path=executable_path,
                )
            else:
                browser = playwright.chromium.launch(headless=False)

            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector(REPORT_TYPE_SELECTOR, timeout=30000)
            page.select_option(REPORT_TYPE_SELECTOR, "1")
            page.wait_for_selector(f"xpath={PERIOD_HEADER_SELECTOR}", timeout=30000)
            page.wait_for_timeout(1000)

            period_header_text = _get_xpath_text(page, PERIOD_HEADER_SELECTOR)
            period, fiscal_year, fiscal_quarter = _parse_period_header(period_header_text)
            values = _collect_values(page)

            if not any(values.values()):
                raise ValueError("Income statement data could not be extracted from Stockbit")

            return {
                "status": "ok",
                "symbol": symbol,
                "period": period,
                "fiscalYear": fiscal_year,
                "fiscalQuarter": fiscal_quarter,
                "periodEndDate": _period_end_date(period, fiscal_year),
                "currency": "IDR",
                "auditStatus": "UNAUDITED",
                "revenue": values.get("revenue"),
                "revenueGrowthYoY": None,
                "cogs": values.get("cogs"),
                "grossProfit": values.get("grossProfit"),
                "operatingExpenses": values.get("operatingExpenses"),
                "sellingExpenses": None,
                "generalAdminExpenses": values.get("generalAdminExpenses"),
                "rdExpenses": None,
                "depreciationAmort": None,
                "ebit": None,
                "ebitda": values.get("ebitda"),
                "operatingIncome": None,
                "interestExpense": values.get("interestExpense"),
                "interestIncome": values.get("interestIncome"),
                "otherNonOperatingIncome": values.get("otherNonOperatingIncome"),
                "pretaxIncome": values.get("pretaxIncome"),
                "incomeTaxExpense": values.get("incomeTaxExpense"),
                "effectiveTaxRate": None,
                "netIncome": values.get("netIncome"),
                "netIncomeAttributable": values.get("netIncomeAttributable"),
                "minorityInterest": values.get("minorityInterest"),
                "eps": values.get("eps"),
                "epsDiluted": None,
                "sharesWeightedAvg": values.get("sharesWeightedAvg"),
            }
    except PlaywrightTimeoutError as exc:
        raise ValueError(f"Timeout while scraping Stockbit for symbol {symbol}: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Failed to scrape Stockbit income statement: {exc}") from exc
