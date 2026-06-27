from pathlib import Path

# URL Templates
URL_TEMPLATE = "https://stockbit.com/symbol/{symbol}/financials"

# Selectors
REPORT_TYPE_SELECTOR = 'select[data-cy="report-type"]'
STATEMENT_TYPE_SELECTOR = 'select[data-cy="statement-type"]'
DATA_TABLE_SELECTOR = "#data_table_1"
FINANCIAL_WRAPPER = 'div[data-cy="financial-table"]'

# Session popup selectors
SESSION_EXPIRED_MODAL = '.modal-error-social'
SESSION_EXPIRED_TITLE = 'p[data-cy="error-trading-modal-title"]'

# Browser executables
CHROME_EXECUTABLES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
]

BRAVE_EXECUTABLES = [
    Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
    Path(r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"),
]

BROWSER_EXECUTABLES = CHROME_EXECUTABLES + BRAVE_EXECUTABLES

# Report types
REPORT_TYPES = {
    "income_statement": "1",
    "balance_sheet": "2",
    "cash_flow": "3",
}

# Statement types
STATEMENT_TYPES = {
    "quarterly": "1",
    "annual": "2",
    "ttm": "3",
    "interim_ytd": "4",
}

# Field mappings untuk Income Statement
INCOME_STATEMENT_FIELDS = {
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
    "netIncome": "Net Income Attributable To",
    "minorityInterest": "Non-Controlling Interests",
    "netIncomeAttributable": "Owners Of The Company",
    "eps": "EPS (Quarter)",
    "sharesWeightedAvg": "Share Outstanding",
    "ebitda": "EBITDA (Quarter)",
}

# Field mappings untuk Balance Sheet (template)
BALANCE_SHEET_FIELDS = {
    "totalAssets": "Total Assets",
    "totalLiabilities": "Total Liabilities",
    "totalEquity": "Total Equity",
    # Tambahkan field lainnya sesuai kebutuhan
}

# Field mappings untuk Cash Flow (template)
CASH_FLOW_FIELDS = {
    "operatingCashFlow": "Cash Flow From Operating Activities",
    "investingCashFlow": "Cash Flow From Investing Activities",
    "financingCashFlow": "Cash Flow From Financing Activities",
    # Tambahkan field lainnya sesuai kebutuhan
}