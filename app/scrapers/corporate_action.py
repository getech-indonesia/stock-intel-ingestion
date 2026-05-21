from __future__ import annotations

from app.scrapers.common import HEADERS, _get_json_cloudscraper

IDX_CORPORATE_ACTION_URL = "https://www.idx.co.id/primary/ListingActivity/GetIssuedHistory"


def fetch_idx_corporate_action(
    ca_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    start: int = 0,
    length: int = 9999,
) -> dict:
    payload = _get_json_cloudscraper(
        IDX_CORPORATE_ACTION_URL,
        params={
            "caType": str(ca_type or "").strip(),
            "dateFrom": str(date_from or "").strip(),
            "dateTo": str(date_to or "").strip(),
            "start": int(start),
            "length": int(length),
        },
        headers=HEADERS,
    )

    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected IDX corporate action response format.")

    data = payload.get("data") or []
    if not isinstance(data, list):
        data = []

    normalized = dict(payload)
    normalized["data"] = data
    normalized["recordsTotal"] = payload.get("recordsTotal") or len(data)
    normalized["recordsFiltered"] = payload.get("recordsFiltered") or normalized["recordsTotal"]
    return normalized