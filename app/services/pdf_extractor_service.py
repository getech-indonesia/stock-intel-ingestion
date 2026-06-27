import json
from typing import Any, Dict, List, Optional
from app.scrapers.common import _download_file, _extract_attachment_text
from utils.ai import _build_client, _safe_json_parse
from config.settings import OPENAI_MODEL

# Template structures matching user requested JSON schema
DEFAULT_INCOME_STATEMENT = {
    "period": "Q1",
    "fiscalYear": 2026,
    "fiscalQuarter": 1,
    "periodEndDate": "",
    "currency": "IDR",
    "auditStatus": "UNAUDITED",
    "revenue": 0,
    "revenueGrowthYoY": None,
    "cogs": None,
    "grossProfit": None,
    "operatingExpenses": None,
    "sellingExpenses": None,
    "generalAdminExpenses": None,
    "rdExpenses": None,
    "depreciationAmort": None,
    "ebit": None,
    "ebitda": None,
    "operatingIncome": None,
    "interestExpense": None,
    "interestIncome": None,
    "otherNonOperatingIncome": None,
    "pretaxIncome": None,
    "incomeTaxExpense": None,
    "effectiveTaxRate": None,
    "netIncome": 0,
    "netIncomeAttributable": None,
    "minorityInterest": None,
    "eps": None,
    "epsDiluted": None,
    "sharesWeightedAvg": None
}

DEFAULT_BALANCE_SHEET = {
    "period": "Q1",
    "fiscalYear": 2026,
    "fiscalQuarter": 1,
    "periodEndDate": "",
    "currency": "IDR",
    "auditStatus": "UNAUDITED",
    "cash": None,
    "shortTermInvestments": None,
    "accountsReceivable": None,
    "inventory": None,
    "otherCurrentAssets": None,
    "totalCurrentAssets": None,
    "propertyPlantEquipment": None,
    "intangibleAssets": None,
    "goodwill": None,
    "longTermInvestments": None,
    "otherNonCurrentAssets": None,
    "totalNonCurrentAssets": None,
    "totalAssets": 0,
    "shortTermDebt": None,
    "accountsPayable": None,
    "deferredRevenue": None,
    "otherCurrentLiabilities": None,
    "totalCurrentLiabilities": None,
    "longTermDebt": None,
    "deferredTaxLiabilities": None,
    "otherNonCurrentLiabilities": None,
    "totalNonCurrentLiabilities": None,
    "totalLiabilities": None,
    "commonStock": None,
    "additionalPaidInCapital": None,
    "retainedEarnings": None,
    "treasuryStock": None,
    "otherEquity": None,
    "minorityInterestEquity": None,
    "totalEquity": 0,
    "bookValuePerShare": None,
    "netDebt": None,
    "workingCapital": None
}

DEFAULT_CASH_FLOW = {
    "period": "Q1",
    "fiscalYear": 2026,
    "fiscalQuarter": 1,
    "periodEndDate": "",
    "currency": "IDR",
    "auditStatus": "UNAUDITED",
    "netIncomeStart": None,
    "depreciationAmort": None,
    "stockBasedCompensation": None,
    "changeInWorkingCapital": None,
    "changeInReceivables": None,
    "changeInInventory": None,
    "changeInPayables": None,
    "otherOperatingActivities": None,
    "netCashFromOperations": 0,
    "capitalExpenditures": None,
    "acquisitions": None,
    "purchaseOfInvestments": None,
    "saleOfInvestments": None,
    "otherInvestingActivities": None,
    "netCashFromInvesting": None,
    "debtIssuance": None,
    "debtRepayment": None,
    "commonStockIssuance": None,
    "commonStockRepurchase": None,
    "dividendsPaid": None,
    "otherFinancingActivities": None,
    "netCashFromFinancing": None,
    "netChangeInCash": None,
    "cashBeginningPeriod": None,
    "cashEndPeriod": None,
    "freeCashFlow": None
}


def _coerce_number(val: Any) -> Optional[float | int]:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return val
    try:
        s = str(val).replace(",", "").strip()
        if "." in s:
            return float(s)
        return int(s)
    except Exception:
        return None


def _merge_and_coerce(extracted_item: dict, template: dict) -> dict:
    merged = {}
    for key, default_val in template.items():
        extracted_val = extracted_item.get(key)
        
        # If the key is not in response, use the default value
        if extracted_val is None:
            merged[key] = default_val
            continue
            
        # Coerce values based on template type or logical fields
        if default_val is None or isinstance(default_val, (int, float)):
            coerced = _coerce_number(extracted_val)
            if coerced is None:
                # If template has a non-None default (like 0), keep it
                merged[key] = default_val
            else:
                merged[key] = coerced
        else:
            merged[key] = str(extracted_val).strip()
            
    return merged


def extract_financial_report_from_pdf(pdf_url: str) -> dict:
    """
    Downloads a PDF from the given URL, extracts text,
    uses ChatGPT to extract and screen the financial data,
    and returns a structured JSON matching the user schema.
    """
    # 1. Download the PDF
    try:
        content = _download_file(pdf_url)
    except Exception as exc:
        raise ValueError(f"Failed to download PDF from URL: {exc}")

    # 2. Extract text from PDF
    try:
        extracted_text = _extract_attachment_text("report.pdf", content)
    except Exception as exc:
        raise ValueError(f"Failed to extract text from PDF: {exc}")

    if not extracted_text or not extracted_text.strip():
        raise ValueError("PDF content is empty or contains no extractable text")

    # Limit to first 80,000 characters to prevent token limit issues
    trimmed_text = extracted_text[:80000]

    # 3. Prompt ChatGPT
    prompt = f"""
You are an expert financial analyst. Extract all financial statements (income statement, balance sheet, and cash flow statement) for the company mentioned in the text document.

CRITICAL RULES:
1. DETECT THE SCALE/MULTIPLIER: Detect if the numbers in the document are in millions (jutaan), thousands (ribuan), billions (miliaran), or units (satuan). You MUST scale all numeric values to full units (e.g., if currency is IDR and the table is in millions, multiply each number by 1,000,000. So "14,146,990" becomes 14146990000000). Return the final scaled numbers.
2. STOCK SYMBOL: Find the stock symbol/ticker (e.g. BBCA, BBRI, TLKM, ASII) of the company from the document and return it in the "symbol" field.
3. CONFIDENCE SCORE: Estimate your extraction confidence as an integer between 0 and 100 in the "confident" field (representing percentage).
4. PERIOD AND QUARTER:
   - Identify the period ("Q1", "Q2", "Q3", "Q4").
   - Identify the fiscalYear (e.g. 2026).
   - Identify the fiscalQuarter (1 for Q1, 2 for Q2, 3 for Q3, 4 for Q4).
   - Identify the periodEndDate ("YYYY-MM-DD" or empty string if not found).
   - Identify the currency (e.g., "IDR", "USD").
   - Identify the auditStatus ("AUDITED" or "UNAUDITED").
5. NULL VALUES: If a field is not mentioned or not applicable, set its value to null. Do not guess.
6. Return ONLY a valid JSON object matching the JSON schema below. Do not include markdown code fences (like ```json) or any comments outside the JSON.

JSON SCHEMA:
{{
  "symbol": "STOCK_SYMBOL",
  "confident": 99,
  "incomeStatements": [
    {{
      "period": "Q1" | "Q2" | "Q3" | "Q4",
      "fiscalYear": integer,
      "fiscalQuarter": 1 | 2 | 3 | 4,
      "periodEndDate": "YYYY-MM-DD",
      "currency": "IDR" | "USD",
      "auditStatus": "AUDITED" | "UNAUDITED",
      "revenue": number or null,
      "revenueGrowthYoY": number or null,
      "cogs": number or null,
      "grossProfit": number or null,
      "operatingExpenses": number or null,
      "sellingExpenses": number or null,
      "generalAdminExpenses": number or null,
      "rdExpenses": number or null,
      "depreciationAmort": number or null,
      "ebit": number or null,
      "ebitda": number or null,
      "operatingIncome": number or null,
      "interestExpense": number or null,
      "interestIncome": number or null,
      "otherNonOperatingIncome": number or null,
      "pretaxIncome": number or null,
      "incomeTaxExpense": number or null,
      "effectiveTaxRate": number or null,
      "netIncome": number or null,
      "netIncomeAttributable": number or null,
      "minorityInterest": number or null,
      "eps": number or null,
      "epsDiluted": number or null,
      "sharesWeightedAvg": number or null
    }}
  ],
  "balanceSheets": [
    {{
      "period": "Q1" | "Q2" | "Q3" | "Q4",
      "fiscalYear": integer,
      "fiscalQuarter": 1 | 2 | 3 | 4,
      "periodEndDate": "YYYY-MM-DD",
      "currency": "IDR" | "USD",
      "auditStatus": "AUDITED" | "UNAUDITED",
      "cash": number or null,
      "shortTermInvestments": number or null,
      "accountsReceivable": number or null,
      "inventory": number or null,
      "otherCurrentAssets": number or null,
      "totalCurrentAssets": number or null,
      "propertyPlantEquipment": number or null,
      "intangibleAssets": number or null,
      "goodwill": number or null,
      "longTermInvestments": number or null,
      "otherNonCurrentAssets": number or null,
      "totalNonCurrentAssets": number or null,
      "totalAssets": number or null,
      "shortTermDebt": number or null,
      "accountsPayable": number or null,
      "deferredRevenue": number or null,
      "otherCurrentLiabilities": number or null,
      "totalCurrentLiabilities": number or null,
      "longTermDebt": number or null,
      "deferredTaxLiabilities": number or null,
      "otherNonCurrentLiabilities": number or null,
      "totalNonCurrentLiabilities": number or null,
      "totalLiabilities": number or null,
      "commonStock": number or null,
      "additionalPaidInCapital": number or null,
      "retainedEarnings": number or null,
      "treasuryStock": number or null,
      "otherEquity": number or null,
      "minorityInterestEquity": number or null,
      "totalEquity": number or null,
      "bookValuePerShare": number or null,
      "netDebt": number or null,
      "workingCapital": number or null
    }}
  ],
  "cashFlows": [
    {{
      "period": "Q1" | "Q2" | "Q3" | "Q4",
      "fiscalYear": integer,
      "fiscalQuarter": 1 | 2 | 3 | 4,
      "periodEndDate": "YYYY-MM-DD",
      "currency": "IDR" | "USD",
      "auditStatus": "AUDITED" | "UNAUDITED",
      "netIncomeStart": number or null,
      "depreciationAmort": number or null,
      "stockBasedCompensation": number or null,
      "changeInWorkingCapital": number or null,
      "changeInReceivables": number or null,
      "changeInInventory": number or null,
      "changeInPayables": number or null,
      "otherOperatingActivities": number or null,
      "netCashFromOperations": number or null,
      "capitalExpenditures": number or null,
      "acquisitions": number or null,
      "purchaseOfInvestments": number or null,
      "saleOfInvestments": number or null,
      "otherInvestingActivities": number or null,
      "netCashFromInvesting": number or null,
      "debtIssuance": number or null,
      "debtRepayment": number or null,
      "commonStockIssuance": number or null,
      "commonStockRepurchase": number or null,
      "dividendsPaid": number or null,
      "otherFinancingActivities": number or null,
      "netCashFromFinancing": number or null,
      "netChangeInCash": number or null,
      "cashBeginningPeriod": number or null,
      "cashEndPeriod": number or null,
      "freeCashFlow": number or null
    }}
  ]
}}

TEXT DOCUMENT:
{trimmed_text}
"""

    client = _build_client()
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a precise financial report extraction assistant. Return ONLY a valid JSON object matching the requested schema.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or ""
    parsed = _safe_json_parse(content)

    # 4. Standardize and merge with default schema to guarantee structure
    symbol = str(parsed.get("symbol") or "UNKNOWN").strip().upper()
    confident_val = parsed.get("confident")
    if confident_val is not None:
        try:
            confident = int(_coerce_number(confident_val) or 0)
        except Exception:
            confident = 0
    else:
        confident = 0

    income_statements = []
    for item in (parsed.get("incomeStatements") or []):
        income_statements.append(_merge_and_coerce(item, DEFAULT_INCOME_STATEMENT))

    balance_sheets = []
    for item in (parsed.get("balanceSheets") or []):
        balance_sheets.append(_merge_and_coerce(item, DEFAULT_BALANCE_SHEET))

    cash_flows = []
    for item in (parsed.get("cashFlows") or []):
        cash_flows.append(_merge_and_coerce(item, DEFAULT_CASH_FLOW))

    return {
        "symbol": symbol,
        "confident": confident,
        "incomeStatements": income_statements,
        "balanceSheets": balance_sheets,
        "cashFlows": cash_flows
    }
