from __future__ import annotations

from typing import Any, Dict


def serialize_emiten_list(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "ok",
        "mode": result.get("mode", "list"),
        "pagination": result.get("pagination") or {},
        "items": result.get("items") or [],
    }


def serialize_emiten_detail(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "ok",
        "mode": result.get("mode", "detail"),
        "symbol": result.get("symbol"),
        "source_page": result.get("source_page") or {},
        "item": result.get("item") or {},
    }
