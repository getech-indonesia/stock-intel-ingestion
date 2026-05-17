from typing import Dict, Any
from utils.helper import _pick_first, _normalize_shareholder_response


def build_response(fundamental_data: Dict[str, Any], symbol: str, year: int, request_period: str, summary: str) -> Dict[str, Any]:
    parsed_data = fundamental_data.get("data") or {}
    raw_data = fundamental_data.get("raw_response") or {}
    attachments = raw_data.get("Attachments") or []
    first_attachment = attachments[0] if attachments else {}

    nama_emiten = _pick_first(
        fundamental_data.get("nama_emiten"),
        parsed_data.get("nama_emiten"),
        raw_data.get("NamaEmiten"),
        first_attachment.get("NamaEmiten"),
    )

    sektor = _pick_first(
        fundamental_data.get("sector"),
        parsed_data.get("sector"),
        raw_data.get("Sector"),
        raw_data.get("Sektor"),
    )

    sub_sektor = _pick_first(
        fundamental_data.get("sub_sector"),
        parsed_data.get("sub_sector"),
        raw_data.get("SubSector"),
        raw_data.get("Sub_Sector"),
        raw_data.get("SubSektor"),
    )

    tanggal_laporan = _pick_first(
        fundamental_data.get("report_date"),
        parsed_data.get("tanggal_laporan"),
        raw_data.get("TanggalLaporan"),
        raw_data.get("Report_Date"),
        raw_data.get("File_Modified"),
    )

    current_data = parsed_data

    response = {
        "meta": {
            "kode_emiten": _pick_first(fundamental_data.get("symbol"), parsed_data.get("kode_emiten")),
            "nama_emiten": nama_emiten,
            "sektor": sektor,
            "sub_sektor": sub_sektor,
            "periode": request_period,
            "tahun": year,
            "tanggal_laporan": tanggal_laporan,
        },
        "financials": {
            "revenue": current_data.get("revenue"),
            "net_income": _pick_first(current_data.get("net_income"), current_data.get("net_profit")),
            "operating_profit": current_data.get("operating_profit"),
            "operating_expense": current_data.get("operating_expense"),
            "total_assets": current_data.get("total_assets"),
            "total_equity": current_data.get("total_equity"),
            "total_liabilities": current_data.get("total_liabilities"),
        },
        "market": {
            "price": current_data.get("price"),
            "shares_outstanding": current_data.get("shares_outstanding"),
            "market_cap": current_data.get("market_cap"),
        },
        "ratios": {
            "profitability": {
                "roe": current_data.get("roe"),
                "roa": current_data.get("roa"),
                "net_margin": current_data.get("npm"),
            },
            "leverage": {"debt_to_equity": current_data.get("der")},
            "liquidity": {"current_ratio": current_data.get("current_ratio")},
            "valuation": {
                "eps": current_data.get("eps"),
                "book_value_per_share": current_data.get("book_value_per_share"),
                "per": current_data.get("per"),
                "pbr": current_data.get("pbr"),
            },
        },
        "growth": {
            "revenue_yoy": (fundamental_data.get("growth") or {}).get("revenue_yoy"),
            "net_income_yoy": (fundamental_data.get("growth") or {}).get("net_income_yoy"),
        },
        "raw_flags": {
            "has_cogs": current_data.get("has_cogs", False),
            "has_current_assets": current_data.get("has_current_assets", False),
        },
        "shareholder": fundamental_data.get("shareholder"),
        "ai_summary": summary,
    }

    response = _normalize_shareholder_response(response)
    return response
