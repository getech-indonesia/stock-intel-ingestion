from flask import current_app
from typing import Optional

from app.scrapers.fundamental import scrape_fundamental, find_shareholders
from app.db import get_fundamental_result, save_fundamental_result
from utils.ai import summarize_fundamental, extract_financial_metrics
from utils.market import fetch_market_snapshot
from utils.helper import (
    _pick_first,
    _to_number,
    _normalize_shareholder_entry,
    _normalize_shareholder_response,
    _enrich_growth,
    _normalize_current_data,
)

from app.serializers.fundamental_serializer import build_response


def fetch_and_build_fundamental(symbol: str, year: int, quarter: Optional[str]):
    request_period = quarter or "AUDIT"

    # try cached
    try:
        cached_payload = get_fundamental_result(symbol, year, request_period)
        if cached_payload:
            cached_payload = _normalize_shareholder_response(cached_payload)
            cached_largest = ((cached_payload.get("shareholder") or {}).get("largest") or [])
            if isinstance(cached_largest, list) and not cached_largest:
                current_app.logger.info(
                    "Cached payload has empty shareholder list for %s %s %s, refreshing from source.",
                    symbol,
                    year,
                    request_period,
                )
                cached_payload = None

        if cached_payload:
            current_app.logger.info(
                "Returning cached fundamental payload from database for %s %s %s",
                symbol,
                year,
                request_period,
            )
            return cached_payload
    except Exception as exc:
        current_app.logger.warning(
            "Database lookup failed for %s %s %s, continuing with scrape: %s",
            symbol,
            year,
            request_period,
            exc,
        )

    try:
        fundamental_data = scrape_fundamental(symbol, year, quarter)
    except Exception:
        raise

    report_text = fundamental_data.get("report_text") or ""
    shareholders = []

    if report_text:
        try:
            extracted_shareholders = find_shareholders(report_text)
        except Exception as exc:
            current_app.logger.warning(
                "Shareholder screening from report failed for %s %s %s: %s",
                symbol,
                year,
                request_period,
                exc,
            )
            extracted_shareholders = []

        if isinstance(extracted_shareholders, list):
            for item in extracted_shareholders:
                normalized_item = _normalize_shareholder_entry(item)
                if normalized_item:
                    shareholders.append(normalized_item)
        if shareholders:
            shareholders.sort(key=lambda item: item.get("shares") or 0, reverse=True)

    # fallback AI only when report does not provide valid shareholder rows
    if not shareholders:
        try:
            from utils.ai import extract_shareholders_ai

            ai_data = extract_shareholders_ai(fundamental_data)
        except Exception as exc:
            current_app.logger.warning(
                "AI shareholder extraction failed for %s %s %s: %s",
                symbol,
                year,
                request_period,
                exc,
            )
            ai_data = []

        if isinstance(ai_data, list):
            for item in ai_data:
                normalized_item = _normalize_shareholder_entry(item)
                if normalized_item:
                    shareholders.append(normalized_item)
            if shareholders:
                shareholders.sort(key=lambda item: item.get("shares") or 0, reverse=True)

    fundamental_data["shareholder"] = {"largest": shareholders if isinstance(shareholders, list) else [],}

    market_snapshot = fetch_market_snapshot(symbol)

    # EXISTING EXTRACTION
    try:
        extracted_metrics = extract_financial_metrics(fundamental_data)
        current_data = fundamental_data.get("data") or {}

        for key, value in extracted_metrics.items():
            if current_data.get(key) in (None, "") and value not in (None, ""):
                current_data[key] = value

        fundamental_data["data"] = current_data
    except Exception:
        current_data = fundamental_data.get("data") or {}

    for key, value in market_snapshot.items():
        if value not in (None, ""):
            current_data[key] = value

    current_app.logger.info("Market snapshot merged for %s: %s", symbol, market_snapshot)

    # Calculation layer (safe additions)
    try:
        revenue = current_data.get("revenue")
        net_income = current_data.get("net_profit")
        total_assets = current_data.get("total_assets")
        total_equity = current_data.get("total_equity")
        total_liabilities = current_data.get("total_liabilities")
        shares = current_data.get("shares_outstanding")
        price = current_data.get("price")

        # NPM
        if current_data.get("npm") in (None, "") and revenue and net_income:
            try:
                current_data["npm"] = round((net_income / revenue) * 100, 2)
            except Exception:
                pass

        # Total Liabilities
        if current_data.get("total_liabilities") in (None, "") and total_assets and total_equity:
            try:
                current_data["total_liabilities"] = total_assets - total_equity
            except Exception:
                pass

        # Operating Profit (fallback)
        if current_data.get("operating_profit") in (None, ""):
            try:
                revenue_value = _to_number(revenue)
                operating_expense_value = _to_number(current_data.get("operating_expense"))
                if revenue_value is not None and operating_expense_value is not None:
                    current_data["operating_profit"] = revenue_value - operating_expense_value
            except Exception:
                pass

        # Current Ratio
        if current_data.get("current_ratio") in (None, ""):
            try:
                current_assets = _to_number(_pick_first(current_data.get("current_assets"), total_assets))
                current_liabilities = _to_number(_pick_first(current_data.get("current_liabilities"), total_liabilities))
                if current_liabilities not in (None, 0) and current_assets is not None:
                    current_data["current_ratio"] = round(current_assets / current_liabilities, 4)
            except Exception:
                pass

        # DER
        if current_data.get("der") in (None, ""):
            try:
                liabilities_value = _to_number(_pick_first(current_data.get("total_liabilities"), total_liabilities))
                equity_value = _to_number(total_equity)
                if liabilities_value is not None and equity_value not in (None, 0):
                    current_data["der"] = round(liabilities_value / equity_value, 4)
            except Exception:
                pass

        # ROA
        if current_data.get("roa") in (None, ""):
            try:
                net_income_value = _to_number(net_income)
                assets_value = _to_number(total_assets)
                if net_income_value is not None and assets_value not in (None, 0):
                    current_data["roa"] = round((net_income_value / assets_value) * 100, 2)
            except Exception:
                pass

        # ROE
        if current_data.get("roe") in (None, ""):
            try:
                net_income_value = _to_number(net_income)
                equity_value = _to_number(total_equity)
                if net_income_value is not None and equity_value not in (None, 0):
                    current_data["roe"] = round((net_income_value / equity_value) * 100, 2)
            except Exception:
                pass

        # EPS
        if current_data.get("eps") in (None, "") and net_income and shares:
            try:
                current_data["eps"] = net_income / shares
            except Exception:
                pass

        # BVPS
        if current_data.get("book_value_per_share") in (None, "") and total_equity and shares:
            try:
                current_data["book_value_per_share"] = total_equity / shares
            except Exception:
                pass

        # PER
        if current_data.get("per") in (None, "") and price and current_data.get("eps"):
            try:
                current_data["per"] = price / current_data.get("eps")
            except Exception:
                pass

        # PBR
        if current_data.get("pbr") in (None, "") and price and current_data.get("book_value_per_share"):
            try:
                current_data["pbr"] = price / current_data.get("book_value_per_share")
            except Exception:
                pass

    except Exception:
        pass

    fundamental_data = _enrich_growth(fundamental_data, symbol, year, quarter)
    current_data = _normalize_current_data(fundamental_data.get("data") or {})
    if current_data:
        fundamental_data["data"] = current_data

    # AI summary
    try:
        summary = summarize_fundamental(fundamental_data)
    except Exception as e:
        current_app.logger.error(
            "Failed to generate AI summary for %s %d %s: %s",
            symbol,
            year,
            request_period,
            str(e),
        )
        summary = "AI summarization is currently unavailable. Please try again later."

    response = build_response(fundamental_data, symbol, year, request_period, summary)

    # save result (best-effort)
    try:
        save_fundamental_result(response)
    except Exception:
        pass

    return response
