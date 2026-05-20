from __future__ import annotations

from app.scrapers.common import HEADERS, _get_json_cloudscraper

IDX_STOCK_PRICE_URL = "https://www.idx.co.id/primary/ListedCompany/GetTradingInfoSS"


def fetch_idx_stock_price(symbol: str, start: int = 0, length: int = 2000) -> dict:
    normalized_symbol = str(symbol or "").strip().upper()
    if not normalized_symbol:
        raise ValueError("Invalid symbol.")

    payload = _get_json_cloudscraper(
        IDX_STOCK_PRICE_URL,
        params={
            "code": normalized_symbol,
            "start": int(start),
            "length": int(length),
        },
        headers=HEADERS,
    )

    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected IDX stock price response format.")

    replies = payload.get("replies") or payload.get("Replies") or []
    if not isinstance(replies, list):
        replies = []

    normalized = dict(payload)
    normalized["KodeEmiten"] = normalized_symbol
    normalized["replies"] = replies
    return normalized
