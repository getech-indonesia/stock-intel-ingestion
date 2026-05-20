from __future__ import annotations

from app.scrapers.common import BASE_URL, HEADERS, _download_file, _extract_attachment_text, _extract_pdf_text, _get

QUARTER_MAP = {
    "Q1": "tw1",
    "Q2": "tw2",
    "Q3": "tw3",
    "Q4": "tw4",
}

SUPPORTED_EXTENSIONS = {".pdf", ".xlsx", ".xls"}
MAX_ATTACHMENTS_TO_PARSE = 4
MAX_CHARS_PER_FILE = 8000
MAX_TOTAL_CHARS = 14000

PRIORITY_KEYWORDS = [
    "financial",
    "keuangan",
    "laporan-keuangan",
    "quarter",
    "kuartal",
    "interim",
]
LOW_PRIORITY_KEYWORDS = [
    "esg",
    "sustainability",
    "keberlanjutan",
]

FINANCIAL_TEXT_KEYWORDS = [
    "jumlah aset",
    "total assets",
    "jumlah liabilitas",
    "total liabilities",
    "jumlah ekuitas",
    "total equity",
    "pendapatan",
    "revenue",
    "laba operasional",
    "operating profit",
    "laba bersih",
    "net profit",
    "laba tahun berjalan",
    "profit for the period",
    "beban operasional",
    "operating expense",
    "net interest income",
    "current ratio",
    "debt to equity",
    "return on assets",
    "return on equity",
    "eps",
    "book value per share",
]

SHAREHOLDER_TEXT_KEYWORDS = [
    "pemegang saham",
    "shareholder",
    "komposisi pemegang saham",
    "composition of shareholders",
    "jumlah lembar saham",
    "number of shares",
    "persentase kepemilikan",
    "percentage of ownership",
    "kepemilikan saham",
    "share ownership",
    "daftar pemegang",
]


def _collect_report_text(raw_data: dict) -> tuple[str, list[dict]]:
    attachments = raw_data.get("Attachments") or []
    eligible = []

    for item in attachments:
        file_name = str(item.get("File_Name") or "")
        ext = str(item.get("File_Type") or "").lower()
        if not ext and "." in file_name:
            ext = "." + file_name.lower().split(".")[-1]
        if ext in SUPPORTED_EXTENSIONS:
            eligible.append(item)

    def score_attachment(item: dict) -> int:
        file_name = str(item.get("File_Name") or "").lower()
        score = 0
        for kw in PRIORITY_KEYWORDS:
            if kw in file_name:
                score += 3
        for kw in LOW_PRIORITY_KEYWORDS:
            if kw in file_name:
                score -= 2
        return score

    eligible.sort(key=score_attachment, reverse=True)

    parsed_docs = []
    text_chunks = []
    total_chars = 0

    for item in eligible[:MAX_ATTACHMENTS_TO_PARSE]:
        file_name = str(item.get("File_Name") or "unknown")
        file_path = str(item.get("File_Path") or "")
        file_url = file_path if file_path.startswith("http") else f"{BASE_URL}{file_path}"

        try:
            content = _download_file(file_url)
            extracted = _extract_attachment_text(file_name, content)
            extracted = _focus_financial_text(extracted)
        except Exception:
            extracted = ""

        extracted = extracted.strip()
        extracted = extracted[:MAX_CHARS_PER_FILE]

        parsed_docs.append(
            {
                "file_name": file_name,
                "file_type": item.get("File_Type"),
                "file_url": file_url,
                "extracted_chars": len(extracted),
            }
        )

        if extracted:
            remaining = MAX_TOTAL_CHARS - total_chars
            if remaining <= 0:
                break
            excerpt = extracted[:remaining]
            total_chars += len(excerpt)
            text_chunks.append(f"### Dokumen: {file_name}\n{excerpt}")

    return "\n\n".join(text_chunks).strip(), parsed_docs


def _focus_financial_text(raw_text: str) -> str:
    lines = [line.strip() for line in (raw_text or "").splitlines() if line.strip()]
    if not lines:
        return ""

    selected_indexes = set()
    for i, line in enumerate(lines):
        lower_line = line.lower()
        has_metric_keyword = any(keyword in lower_line for keyword in FINANCIAL_TEXT_KEYWORDS)
        has_numeric_value = any(char.isdigit() for char in line)
        if has_metric_keyword and has_numeric_value:
            selected_indexes.add(i)
            for offset in (-1, 1):
                j = i + offset
                if 0 <= j < len(lines):
                    selected_indexes.add(j)

        has_shareholder_keyword = any(keyword in lower_line for keyword in SHAREHOLDER_TEXT_KEYWORDS)
        if has_shareholder_keyword:
            for offset in range(-8, 9):
                j = i + offset
                if 0 <= j < len(lines):
                    selected_indexes.add(j)

    if not selected_indexes:
        return "\n".join(lines[:140])

    focused_lines = [lines[i] for i in sorted(selected_indexes)]
    return "\n".join(focused_lines[:300])


def _normalized_lookup(raw_data: dict) -> dict:
    lookup = {}
    for key, value in (raw_data or {}).items():
        normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
        if normalized and normalized not in lookup:
            lookup[normalized] = value
    return lookup


def _pick_field(raw_data: dict, *aliases: str):
    for alias in aliases:
        if alias in raw_data and raw_data.get(alias) not in (None, ""):
            return raw_data.get(alias)

    normalized_lookup = _normalized_lookup(raw_data)
    for alias in aliases:
        normalized = "".join(ch for ch in str(alias).lower() if ch.isalnum())
        value = normalized_lookup.get(normalized)
        if value not in (None, ""):
            return value

    return None


def _fetch_report_results(symbol: str, year: int, periode: str, report_type: str = "rdf") -> list[dict]:
    url = "https://www.idx.co.id/primary/ListedCompany/GetFinancialReport"
    params = {
        "ReportType": report_type,
        "KodeEmiten": symbol.upper(),
        "Year": str(year),
        "SortColumn": "KodeEmiten",
        "SortOrder": "asc",
        "EmitenType": "s",
        "Periode": periode,
        "indexfrom": 1,
        "pagesize": 12,
    }

    response_data = _get(url, params)
    return response_data.get("Results") or []


def get_financial_report(symbol: str, year: int, quarter: str | None = None) -> dict:
    requested_quarter = (quarter or "").strip().upper()
    periode = QUARTER_MAP.get(requested_quarter) if requested_quarter else "audit"

    try:
        results = _fetch_report_results(symbol, year, periode, report_type="rdf")
        if results:
            return results[0]

        fallback_results = _fetch_report_results(symbol, year, periode.upper(), report_type="rdf")
        if fallback_results:
            return fallback_results[0]

        legacy_results = _fetch_report_results(symbol, year, periode, report_type="PDF")
        if legacy_results:
            return legacy_results[0]

        raise RuntimeError(f"No financial data found for {symbol} - {year} {periode}")
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch financial report: {exc}") from exc


def parse_financial_data(raw_data: dict) -> dict:
    return {
        "kode_emiten": _pick_field(raw_data, "KodeEmiten", "Code"),
        "nama_emiten": _pick_field(raw_data, "NamaEmiten", "Name"),
        "periode_laporan": _pick_field(raw_data, "PeriodeLaporan", "Report_Period", "Period"),
        "tanggal_laporan": _pick_field(raw_data, "TanggalLaporan", "Report_Date", "File_Modified", "Date"),
        "sector": _pick_field(raw_data, "Sector", "Sektor"),
        "sub_sector": _pick_field(raw_data, "SubSector", "Sub_Sector", "SubSektor"),
        "revenue": _pick_field(raw_data, "Revenue", "TotalRevenue", "Sales"),
        "cost_of_goods_sold": _pick_field(raw_data, "CostOfGoodsSold", "COGS"),
        "gross_profit": _pick_field(raw_data, "GrossProfit"),
        "operating_expense": _pick_field(raw_data, "OperatingExpense", "OperatingExpenses"),
        "operating_profit": _pick_field(raw_data, "OperatingProfit", "OperatingIncome"),
        "net_profit": _pick_field(raw_data, "NetProfit", "NetIncome", "ProfitForTheYear", "ProfitLoss"),
        "total_assets": _pick_field(raw_data, "TotalAssets", "TotalAsset", "Assets"),
        "total_liabilities": _pick_field(raw_data, "TotalLiabilities", "Liabilities", "TotalLiability"),
        "total_equity": _pick_field(raw_data, "TotalEquity", "Equity"),
        "eps": _pick_field(raw_data, "EPS", "EarningPerShare"),
        "book_value_per_share": _pick_field(raw_data, "BookValuePerShare", "BVPS"),
        "roe": _pick_field(raw_data, "ROE", "ReturnOnEquity"),
        "roa": _pick_field(raw_data, "ROA", "ReturnOnAssets"),
        "npm": _pick_field(raw_data, "NPM", "NetMargin", "NetProfitMargin"),
        "der": _pick_field(raw_data, "DER", "DebtToEquity"),
        "per": _pick_field(raw_data, "PER", "PriceEarningsRatio"),
        "pbr": _pick_field(raw_data, "PBR", "PriceToBookRatio"),
        "current_ratio": _pick_field(raw_data, "CurrentRatio"),
    }


def find_shareholders(data: str) -> list[dict]:
    import re

    if not data:
        return []

    text = data
    matches = list(re.finditer(r"\d{1,3}(?:\.\d{3}){2,}", text))

    if not matches:
        return []

    candidates = []
    seen_shares = set()

    for m in matches:
        raw_number = m.group(0)
        shares = int(raw_number.replace(".", ""))

        if shares < 1_000_000:
            continue
        if shares in seen_shares:
            continue
        seen_shares.add(shares)

        start = max(0, m.start() - 150)
        end = min(len(text), m.end() + 150)
        context = text[start:end]

        percent_match = re.search(r"\b\d{1,3}[,\.]\d{2}\b", context)
        ownership = None
        if percent_match:
            try:
                ownership = float(percent_match.group(0).replace(",", "."))
                if not (0 < ownership <= 100):
                    ownership = None
            except ValueError:
                ownership = None

        before_number = context.split(raw_number)[0]
        lines = [l.strip() for l in before_number.strip().split("\n") if l.strip()]
        name = lines[-1] if lines else ""
        name = re.sub(r"\d[\d\.,]*", "", name).strip()
        name = re.sub(r"\s{2,}", " ", name).strip(" |:-")

        if not name:
            continue

        if not any(k in context.lower() for k in ["pemegang saham", "shareholder", "komposisi pemegang saham"]):
            continue

        if any(bad in context.lower() for bad in ["modal", "penerbitan", "issued", "capital", "treasury"]):
            continue

        candidates.append({
            "name": name,
            "shares": shares,
            "ownership": ownership,
        })

    candidates.sort(key=lambda x: x["shares"], reverse=True)
    return candidates


def find_largest_shareholder(data: str):
    shareholders = find_shareholders(data)
    if not shareholders:
        return None
    return shareholders[0]


def scrape_fundamental(symbol: str, year: int, quarter: str | None = None) -> dict:
    raw_data = get_financial_report(symbol, year, quarter)
    parsed_data = parse_financial_data(raw_data)
    report_text, parsed_documents = _collect_report_text(raw_data)
    request_period = (quarter or "").strip().upper() or "AUDIT"

    return {
        "symbol": symbol.upper(),
        "year": year,
        "quarter": request_period,
        "data": parsed_data,
        "report_text": report_text,
        "report_documents": parsed_documents,
        "raw_response": raw_data,
    }
