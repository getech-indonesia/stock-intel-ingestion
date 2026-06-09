from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional

import requests
from pypdf import PdfReader

from app.scrapers.common import BASE_URL, _download_file, _extract_attachment_text
from app.scrapers.fs_utilities.fs_utils import (
    NUMERIC_ALIASES,
    FIELD_BLOCKED_TOKENS,
    TEXT_BLOCKLIST,
    _normalize_text,
    _to_number,
    _detect_unit_multiplier,
    _to_ratio,
    _attachment_url,
    _text_to_rows,
    _resolve_period,
    _fiscal_quarter,
    _period_end_date,
    _audit_status,
    _find_year_columns,
    _extract_currency,
    _split_pdf_sections,
)
from app.scrapers.fs_utilities.fs_collectors import (
    fetch_financial_report_results,
    _collect_pdf_attachments,
)


def _row_matches_alias(row: list[Any], aliases: list[str]) -> tuple[int, str] | None:
    normalized_aliases = [_normalize_text(alias) for alias in aliases]
    for index, cell in enumerate(row[:6]):
        normalized_cell = _normalize_text(cell)
        if not normalized_cell:
            continue
        raw_label = str(cell or "").strip().lower()
        if any(blocked in raw_label for blocked in TEXT_BLOCKLIST):
            continue
        if any(alias and alias in normalized_cell for alias in normalized_aliases):
            return index, str(cell).strip()
    return None


def _extract_numeric_value(row: list[Any], label_index: int, year_col: int | None, unit_multiplier: float):
    candidates: list[Any] = []

    if year_col is not None and 0 <= year_col < len(row):
        candidates.append(row[year_col])

    for i in range(label_index + 1, min(len(row), label_index + 6)):
        candidates.append(row[i])

    for candidate in candidates:
        if candidate is None:
            continue

        clean_str = str(candidate).replace(".", "").replace(",", ".").replace("(", "-").replace(")", "").strip()
        
        if clean_str in {"2025", "2024", "2023", "2026"}:
            continue

        number = _to_number(clean_str)
        if number is not None:
            if abs(number) < 100:
                continue

            if abs(number) > 1_000_000_000_000:
                return number / 1_000_000

            return number * unit_multiplier

    return None


def _extract_field_numeric(
    rows: list[list[Any]],
    aliases: list[str],
    year_columns: dict[int, int],
    year: int,
    unit_multiplier: float,
    field_name: str | None = None,
):
    year_col = year_columns.get(year)
    blocked_tokens = FIELD_BLOCKED_TOKENS.get(field_name or "", [])
    
    if field_name in ["pretaxIncome", "operatingIncome", "ebit"]:
        for row in rows:
            row_text = " ".join([str(c) for c in row if c]).lower()
            if "laba sebelum pajak penghasilan" in row_text or "income before tax" in row_text:
                if "beban" not in row_text.split("laba sebelum")[0]:
                    value = _extract_numeric_value(row, 0, year_col, unit_multiplier)
                    if value is not None and abs(value) > 1_000_000:
                        return value

    if field_name == "revenue":
        for row in rows:
            row_text = " ".join([str(c) for c in row if c]).lower()
            if "jumlah pendapatan operasional" in row_text or "total operating revenue" in row_text:
                value = _extract_numeric_value(row, 0, year_col, unit_multiplier)
                if value is not None and abs(value) > 1_000_000:
                    return value

    for row in rows:
        matched = _row_matches_alias(row, aliases)
        if not matched:
            continue
        label_index, _ = matched
        normalized_label = _normalize_text(row[label_index])
        if any(token in normalized_label for token in blocked_tokens):
            continue
        value = _extract_numeric_value(row, label_index, year_col, unit_multiplier)
        if value is not None:
            return value
    return None


def _extract_sheet_metrics(rows: list[list[Any]], year: int) -> dict[str, Any]:
    year_columns = _find_year_columns(rows, year)
    unit_multiplier = _detect_unit_multiplier(rows)
    metrics: dict[str, Any] = {}

    for field, aliases in NUMERIC_ALIASES.items():
        value = _extract_field_numeric(rows, aliases, year_columns, year, unit_multiplier, field_name=field)
        if value is not None:
            metrics[field] = value
        else:
            metrics[field] = None

    current_revenue = metrics.get("revenue")
    previous_revenue = None
    if (year - 1) in year_columns:
        previous_revenue = _extract_field_numeric(
            rows,
            NUMERIC_ALIASES["revenue"],
            year_columns,
            year - 1,
            unit_multiplier,
            field_name="revenue",
        )

    if current_revenue not in (None, 0) and previous_revenue not in (None, 0):
        metrics["revenueGrowthYoY"] = round((current_revenue - previous_revenue) / abs(previous_revenue), 6)
    else:
        metrics["revenueGrowthYoY"] = None

    metrics["effectiveTaxRate"] = _to_ratio(metrics.get("effectiveTaxRate"))
    metrics["currency"] = _extract_currency(rows)

    return metrics


def _build_statement_item(result: dict, parsed: dict, fallback_year: int) -> dict:
    fiscal_year = int(result.get("Report_Year") or result.get("report_year") or fallback_year)
    period = _resolve_period(result, "")
    quarter = _fiscal_quarter(period)
    
    return {
        "period": period,
        "fiscalYear": fiscal_year,
        "fiscalQuarter": quarter,
        "periodEndDate": _period_end_date(fiscal_year, quarter),
        "currency": parsed.get("currency") or "IDR",
        "auditStatus": _audit_status(period),
        "revenue": parsed.get("revenue"),
        "revenueGrowthYoY": parsed.get("revenueGrowthYoY"),
        "cogs": parsed.get("cogs"),
        "grossProfit": parsed.get("grossProfit"),
        "operatingExpenses": parsed.get("operatingExpenses"),
        "sellingExpenses": parsed.get("sellingExpenses"),
        "generalAdminExpenses": parsed.get("generalAdminExpenses"),
        "rdExpenses": parsed.get("rdExpenses"),
        "depreciationAmort": parsed.get("depreciationAmort"),
        "ebit": parsed.get("ebit"),
        "ebitda": parsed.get("ebitda"),
        "operatingIncome": parsed.get("operatingIncome"),
        "interestExpense": parsed.get("interestExpense"),
        "interestIncome": parsed.get("interestIncome"),
        "otherNonOperatingIncome": parsed.get("otherNonOperatingIncome"),
        "pretaxIncome": parsed.get("pretaxIncome"),
        "incomeTaxExpense": parsed.get("incomeTaxExpense"),
        "effectiveTaxRate": parsed.get("effectiveTaxRate"),
        "netIncome": parsed.get("netIncome"),
        "netIncomeAttributable": parsed.get("netIncomeAttributable"),
        "minorityInterest": parsed.get("minorityInterest"),
        "eps": parsed.get("eps"),
        "epsDiluted": parsed.get("epsDiluted"),
        "sharesWeightedAvg": parsed.get("sharesWeightedAvg"),
    }


def _normalize_monetary_scale(item: dict) -> dict:
    monetary_fields = [
        "revenue", "cogs", "grossProfit", "operatingExpenses", "sellingExpenses",
        "generalAdminExpenses", "rdExpenses", "depreciationAmort", "ebit", "ebitda",
        "operatingIncome", "interestExpense", "interestIncome", "otherNonOperatingIncome",
        "pretaxIncome", "incomeTaxExpense", "netIncome", "netIncomeAttributable", "minorityInterest",
    ]

    ref_value = 0.0
    for field in ["netIncome", "revenue"]:
        val = item.get(field)
        if isinstance(val, (int, float)) and val != 0:
            ref_value = abs(float(val))
            break

    if ref_value == 0:
        return item

    if ref_value >= 1_000_000_000:
        return item

    if 1_000_000 <= ref_value < 1_000_000_000:
        for field in monetary_fields:
            value = item.get(field)
            if isinstance(value, (int, float)) and value not in (None, 0):
                item[field] = float(value) * 1_000_000

    return item


def _apply_bank_derivations(item: dict, symbol: str) -> dict:
    interest_income = item.get("interestIncome") if isinstance(item.get("interestIncome"), (int, float)) else None
    interest_expense = item.get("interestExpense") if isinstance(item.get("interestExpense"), (int, float)) else None
    operating_income = item.get("operatingIncome") if isinstance(item.get("operatingIncome"), (int, float)) else None
    other_non_op = item.get("otherNonOperatingIncome") or 0.0

    is_bank = any(b_sym in str(symbol).upper() for b_sym in ["BBCA", "BBRI", "BMRI", "BBNI"])
    
    if is_bank:
        item["cogs"] = None
        item["grossProfit"] = None
    else:
        if item.get("cogs") is None and interest_expense is not None:
            item["cogs"] = float(interest_expense)
        if item.get("grossProfit") is None and isinstance(item.get("revenue"), (int, float)) and isinstance(item.get("cogs"), (int, float)):
            item["grossProfit"] = float(item["revenue"]) - float(item["cogs"])

    if item.get("ebit") is None and operating_income is not None:
        item["ebit"] = float(operating_income)

    if item.get("pretaxIncome") is None and operating_income is not None:
        item["pretaxIncome"] = float(operating_income) + float(other_non_op)

    if item.get("incomeTaxExpense") is None and isinstance(item.get("pretaxIncome"), (int, float)) and isinstance(item.get("netIncome"), (int, float)):
        item["incomeTaxExpense"] = float(item["pretaxIncome"]) - float(item["netIncome"])

    if item.get("effectiveTaxRate") is None and isinstance(item.get("incomeTaxExpense"), (int, float)) and isinstance(item.get("pretaxIncome"), (int, float)) and item["pretaxIncome"] not in (0, 0.0):
        item["effectiveTaxRate"] = round(abs(float(item["incomeTaxExpense"])) / abs(float(item["pretaxIncome"])), 6)

    if item.get("effectiveTaxRate") is not None:
            rate = float(item["effectiveTaxRate"])
            if rate > 1.0 or rate < 0.0:
                item["effectiveTaxRate"] = 0.1900

    return item


def scrape_financial_statement_v2(symbol: str, year: int, sector: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Scrape financial statement v2 with strict filtering and sector support
    """
    symbol = symbol.upper()
    results = fetch_financial_report_results(symbol, year)
    report_attachments = _collect_pdf_attachments(results)

    income_items: list[dict] = []
    seen_income_period_year: set[tuple[str, int]] = set()

    for result, attachment in report_attachments:
        file_name = str(attachment.get("File_Name") or attachment.get("file_name") or "")
        file_url = _attachment_url(attachment)
        if not file_url:
            continue

        try:
            content = _download_file(file_url)
            extracted_text = _extract_attachment_text(file_name, content)
            section_text = _split_pdf_sections(extracted_text)
            parsed_income = _extract_sheet_metrics(_text_to_rows(section_text["income"]), year)
            
            resolved_period = _resolve_period(result, file_name)
            resolved_quarter = _fiscal_quarter(resolved_period)

            # Strict month-based validation like v1
            fn_lower = file_name.lower()
            if "mar" in fn_lower or "q1" in fn_lower or "tw1" in fn_lower:
                resolved_period = "Q1"
                resolved_quarter = 1
            elif "jun" in fn_lower or "q2" in fn_lower or "tw2" in fn_lower:
                resolved_period = "Q2"
                resolved_quarter = 2
            elif "sep" in fn_lower or "q3" in fn_lower or "tw3" in fn_lower:
                resolved_period = "Q3"
                resolved_quarter = 3
            elif "dec" in fn_lower or "audit" in fn_lower or "full" in fn_lower:
                resolved_period = "AUDIT"
                resolved_quarter = None

            income_item = _build_statement_item(result, parsed_income, fallback_year=year)
            income_item["period"] = resolved_period
            income_item["fiscalQuarter"] = resolved_quarter
            income_item["periodEndDate"] = _period_end_date(int(income_item["fiscalYear"]), resolved_quarter)
            income_item["auditStatus"] = _audit_status(resolved_period)
        except Exception as e:
            continue

        income_dedup_key = (str(income_item.get("period") or ""), int(income_item.get("fiscalYear") or year))
        if income_dedup_key not in seen_income_period_year:
            seen_income_period_year.add(income_dedup_key)
            income_item = _normalize_monetary_scale(income_item)
            income_item = _apply_bank_derivations(income_item, symbol)
            income_items.append(income_item)

    income_items.sort(key=lambda row: (int(row.get("fiscalYear") or 0), int(row.get("fiscalQuarter") or 99)))

    # Transform to the required output format
    output = []
    for item in income_items:
        period_type = "ANNUAL"
        if item["fiscalQuarter"] == 1:
            period_type = "QUARTERLY"
        elif item["fiscalQuarter"] == 2:
            period_type = "SEMI_ANNUAL"
        elif item["fiscalQuarter"] == 3:
            period_type = "QUARTERLY"

        output.append({
            "companyId": symbol,
            "period": period_type,
            "fiscalYear": item["fiscalYear"],
            "fiscalQuarter": item["fiscalQuarter"],
            "periodEndDate": f"{item['periodEndDate']}T00:00:00.000Z",
            "currency": item["currency"],
            "auditStatus": item["auditStatus"],
            "revenue": item["revenue"],
            "revenueGrowthYoY": item["revenueGrowthYoY"],
            "cogs": item["cogs"],
            "grossProfit": item["grossProfit"],
            "operatingExpenses": item["operatingExpenses"],
            "sellingExpenses": item["sellingExpenses"],
            "generalAdminExpenses": item["generalAdminExpenses"],
            "rdExpenses": item["rdExpenses"],
            "depreciationAmort": item["depreciationAmort"],
            "ebit": item["ebit"],
            "ebitda": item["ebitda"],
            "operatingIncome": item["operatingIncome"],
            "interestExpense": item["interestExpense"],
            "interestIncome": item["interestIncome"],
            "otherNonOperatingIncome": item["otherNonOperatingIncome"],
            "pretaxIncome": item["pretaxIncome"],
            "incomeTaxExpense": item["incomeTaxExpense"],
            "effectiveTaxRate": item["effectiveTaxRate"],
            "netIncome": item["netIncome"],
            "netIncomeAttributable": item["netIncomeAttributable"],
            "minorityInterest": item["minorityInterest"],
            "eps": item["eps"],
            "epsDiluted": item["epsDiluted"],
            "sharesWeightedAvg": item["sharesWeightedAvg"],
        })

    return output
