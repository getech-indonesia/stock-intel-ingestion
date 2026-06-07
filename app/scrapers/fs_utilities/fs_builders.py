from __future__ import annotations

from typing import Any, Dict

from app.scrapers.fs_utilities.fs_utils import _normalize_period, _fiscal_quarter, _period_end_date, _audit_status


def _build_statement_item(result: dict, parsed: dict, fallback_year: int) -> dict:
    fiscal_year = int(result.get("Report_Year") or result.get("report_year") or fallback_year)
    period = _normalize_period(result)
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


def _build_balance_sheet_item(result: dict, parsed: dict, fallback_year: int) -> dict:
    fiscal_year = int(result.get("Report_Year") or result.get("report_year") or fallback_year)
    period = _normalize_period(result)
    quarter = _fiscal_quarter(period)

    return {
        "period": period,
        "fiscalYear": fiscal_year,
        "fiscalQuarter": quarter,
        "periodEndDate": _period_end_date(fiscal_year, quarter),
        "currency": parsed.get("currency") or "IDR",
        "auditStatus": _audit_status(period),
        "cash": parsed.get("cash"),
        "shortTermInvestments": parsed.get("shortTermInvestments"),
        "accountsReceivable": parsed.get("accountsReceivable"),
        "inventory": parsed.get("inventory"),
        "otherCurrentAssets": parsed.get("otherCurrentAssets"),
        "totalCurrentAssets": parsed.get("totalCurrentAssets"),
        "propertyPlantEquipment": parsed.get("propertyPlantEquipment"),
        "intangibleAssets": parsed.get("intangibleAssets"),
        "goodwill": parsed.get("goodwill"),
        "longTermInvestments": parsed.get("longTermInvestments"),
        "otherNonCurrentAssets": parsed.get("otherNonCurrentAssets"),
        "totalNonCurrentAssets": parsed.get("totalNonCurrentAssets"),
        "totalAssets": parsed.get("totalAssets"),
        "shortTermDebt": parsed.get("shortTermDebt"),
        "accountsPayable": parsed.get("accountsPayable"),
        "deferredRevenue": parsed.get("deferredRevenue"),
        "otherCurrentLiabilities": parsed.get("otherCurrentLiabilities"),
        "totalCurrentLiabilities": parsed.get("totalCurrentLiabilities"),
        "longTermDebt": parsed.get("longTermDebt"),
        "deferredTaxLiabilities": parsed.get("deferredTaxLiabilities"),
        "otherNonCurrentLiabilities": parsed.get("otherNonCurrentLiabilities"),
        "totalNonCurrentLiabilities": parsed.get("totalNonCurrentLiabilities"),
        "totalLiabilities": parsed.get("totalLiabilities"),
        "commonStock": parsed.get("commonStock"),
        "additionalPaidInCapital": parsed.get("additionalPaidInCapital"),
        "retainedEarnings": parsed.get("retainedEarnings"),
        "treasuryStock": parsed.get("treasuryStock"),
        "otherEquity": parsed.get("otherEquity"),
        "minorityInterestEquity": parsed.get("minorityInterestEquity"),
        "totalEquity": parsed.get("totalEquity"),
        "bookValuePerShare": parsed.get("bookValuePerShare"),
        "netDebt": parsed.get("netDebt"),
        "workingCapital": parsed.get("workingCapital"),
    }


def _build_cash_flow_item(result: dict, parsed: dict, fallback_year: int) -> dict:
    fiscal_year = int(result.get("Report_Year") or result.get("report_year") or fallback_year)
    period = _normalize_period(result)
    quarter = _fiscal_quarter(period)

    return {
        "period": period,
        "fiscalYear": fiscal_year,
        "fiscalQuarter": quarter,
        "periodEndDate": _period_end_date(fiscal_year, quarter),
        "currency": parsed.get("currency") or "IDR",
        "auditStatus": _audit_status(period),
        "netIncomeStart": parsed.get("netIncomeStart"),
        "depreciationAmort": parsed.get("depreciationAmort"),
        "stockBasedCompensation": parsed.get("stockBasedCompensation"),
        "changeInWorkingCapital": parsed.get("changeInWorkingCapital"),
        "changeInReceivables": parsed.get("changeInReceivables"),
        "changeInInventory": parsed.get("changeInInventory"),
        "changeInPayables": parsed.get("changeInPayables"),
        "otherOperatingActivities": parsed.get("otherOperatingActivities"),
        "netCashFromOperations": parsed.get("netCashFromOperations"),
        "capitalExpenditures": parsed.get("capitalExpenditures"),
        "acquisitions": parsed.get("acquisitions"),
        "purchaseOfInvestments": parsed.get("purchaseOfInvestments"),
        "saleOfInvestments": parsed.get("saleOfInvestments"),
        "otherInvestingActivities": parsed.get("otherInvestingActivities"),
        "netCashFromInvesting": parsed.get("netCashFromInvesting"),
        "debtIssuance": parsed.get("debtIssuance"),
        "debtRepayment": parsed.get("debtRepayment"),
        "commonStockIssuance": parsed.get("commonStockIssuance"),
        "commonStockRepurchase": parsed.get("commonStockRepurchase"),
        "dividendsPaid": parsed.get("dividendsPaid"),
        "otherFinancingActivities": parsed.get("otherFinancingActivities"),
        "netCashFromFinancing": parsed.get("netCashFromFinancing"),
        "netChangeInCash": parsed.get("netChangeInCash"),
        "cashBeginningPeriod": parsed.get("cashBeginningPeriod"),
        "cashEndPeriod": parsed.get("cashEndPeriod"),
        "freeCashFlow": parsed.get("freeCashFlow"),
    }


def _normalize_monetary_scale(item: dict) -> dict:
    monetary_fields = [
        "revenue",
        "cogs",
        "grossProfit",
        "operatingExpenses",
        "sellingExpenses",
        "generalAdminExpenses",
        "rdExpenses",
        "depreciationAmort",
        "ebit",
        "ebitda",
        "operatingIncome",
        "interestExpense",
        "interestIncome",
        "otherNonOperatingIncome",
        "pretaxIncome",
        "incomeTaxExpense",
        "netIncome",
        "netIncomeAttributable",
        "minorityInterest",
    ]

    numeric_values = [
        abs(float(item.get(field)))
        for field in monetary_fields
        if isinstance(item.get(field), (int, float)) and item.get(field) not in (None, 0)
    ]
    if not numeric_values:
        return item

    max_value = max(numeric_values)
    revenue_value = item.get("revenue") if isinstance(item.get("revenue"), (int, float)) else None

    looks_like_millions = (
        str(item.get("currency") or "").upper() == "IDR"
        and max_value < 1_000_000_000
        and (
            max_value >= 1_000_000
            or (revenue_value is not None and 10_000 <= abs(float(revenue_value)) < 1_000_000_000)
        )
    )
    if not looks_like_millions:
        return item

    for field in monetary_fields:
        value = item.get(field)
        if isinstance(value, (int, float)):
            item[field] = float(value) * 1_000_000

    return item


def _normalize_cash_flow_scale(item: dict) -> dict:
    monetary_fields = [
        "netIncomeStart",
        "depreciationAmort",
        "stockBasedCompensation",
        "changeInWorkingCapital",
        "changeInReceivables",
        "changeInInventory",
        "changeInPayables",
        "otherOperatingActivities",
        "netCashFromOperations",
        "capitalExpenditures",
        "acquisitions",
        "purchaseOfInvestments",
        "saleOfInvestments",
        "otherInvestingActivities",
        "netCashFromInvesting",
        "debtIssuance",
        "debtRepayment",
        "commonStockIssuance",
        "commonStockRepurchase",
        "dividendsPaid",
        "otherFinancingActivities",
        "netCashFromFinancing",
        "netChangeInCash",
        "cashBeginningPeriod",
        "cashEndPeriod",
        "freeCashFlow",
    ]

    numeric_values = [
        abs(float(item.get(field)))
        for field in monetary_fields
        if isinstance(item.get(field), (int, float)) and item.get(field) not in (None, 0)
    ]
    if not numeric_values:
        return item

    max_value = max(numeric_values)
    reference_value = item.get("netCashFromOperations") if isinstance(item.get("netCashFromOperations"), (int, float)) else None

    looks_like_millions = (
        str(item.get("currency") or "").upper() == "IDR"
        and max_value < 1_000_000_000
        and (
            max_value >= 1_000_000
            or (reference_value is not None and 10_000 <= abs(float(reference_value)) < 1_000_000_000)
        )
    )
    if not looks_like_millions:
        return item

    for field in monetary_fields:
        value = item.get(field)
        if isinstance(value, (int, float)):
            item[field] = float(value) * 1_000_000

    return item


def _apply_bank_derivations(item: dict) -> dict:
    interest_income = item.get("interestIncome") if isinstance(item.get("interestIncome"), (int, float)) else None
    interest_expense = item.get("interestExpense") if isinstance(item.get("interestExpense"), (int, float)) else None
    revenue = item.get("revenue") if isinstance(item.get("revenue"), (int, float)) else None
    operating_income = item.get("operatingIncome") if isinstance(item.get("operatingIncome"), (int, float)) else None
    other_non_op = item.get("otherNonOperatingIncome")
    if not isinstance(other_non_op, (int, float)):
        other_non_op = 0.0
        item["otherNonOperatingIncome"] = 0.0

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

    if isinstance(item.get("incomeTaxExpense"), (int, float)) and isinstance(item.get("pretaxIncome"), (int, float)):
        if abs(float(item["incomeTaxExpense"]) - float(item["pretaxIncome"])) < 1e-9:
            item["incomeTaxExpense"] = None

    if item.get("netIncome") is None and isinstance(item.get("pretaxIncome"), (int, float)) and isinstance(item.get("incomeTaxExpense"), (int, float)):
        item["netIncome"] = float(item["pretaxIncome"]) - float(item["incomeTaxExpense"])

    if item.get("netIncomeAttributable") is None and isinstance(item.get("netIncome"), (int, float)) and isinstance(item.get("minorityInterest"), (int, float)):
        item["netIncomeAttributable"] = float(item["netIncome"]) - float(item["minorityInterest"])

    if item.get("netIncome") is None and isinstance(item.get("netIncomeAttributable"), (int, float)) and isinstance(item.get("minorityInterest"), (int, float)):
        item["netIncome"] = float(item["netIncomeAttributable"]) + float(item["minorityInterest"])

    if isinstance(item.get("pretaxIncome"), (int, float)) and isinstance(item.get("netIncome"), (int, float)):
        pretax = float(item["pretaxIncome"])
        net = float(item["netIncome"])
        if pretax > 0 and net > pretax * 1.2:
            item["netIncome"] = None
            if isinstance(item.get("netIncomeAttributable"), (int, float)) and isinstance(item.get("minorityInterest"), (int, float)):
                item["netIncome"] = float(item["netIncomeAttributable"]) + float(item["minorityInterest"])

    if item.get("effectiveTaxRate") is None and isinstance(item.get("incomeTaxExpense"), (int, float)) and isinstance(item.get("pretaxIncome"), (int, float)) and item["pretaxIncome"] not in (0, 0.0):
        item["effectiveTaxRate"] = round(abs(float(item["incomeTaxExpense"])) / abs(float(item["pretaxIncome"])), 6)

    if isinstance(item.get("incomeTaxExpense"), (int, float)) and isinstance(item.get("pretaxIncome"), (int, float)):
        if abs(float(item["incomeTaxExpense"])) > abs(float(item["pretaxIncome"])) * 0.9:
            item["incomeTaxExpense"] = None
            item["effectiveTaxRate"] = None

    if (
        isinstance(item.get("pretaxIncome"), (int, float))
        and isinstance(item.get("netIncome"), (int, float))
        and abs(float(item["pretaxIncome"]) - float(item["netIncome"])) < 1e-9
        and item.get("incomeTaxExpense") in (None, 0, 0.0)
    ):
        assumed_rate = 0.2
        pretax = float(item["pretaxIncome"])
        item["incomeTaxExpense"] = round(pretax * assumed_rate, 2)
        item["netIncome"] = round(pretax - item["incomeTaxExpense"], 2)
        item["effectiveTaxRate"] = assumed_rate
        if isinstance(item.get("minorityInterest"), (int, float)):
            item["netIncomeAttributable"] = round(float(item["netIncome"]) - float(item["minorityInterest"]), 2)

    if revenue in (None, 0) and interest_income is not None:
        item["revenue"] = float(interest_income)

    return item
