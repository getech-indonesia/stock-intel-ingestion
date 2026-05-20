from __future__ import annotations

import re
from datetime import datetime

from app.scrapers.common import BASE_URL, HEADERS, _download_file, _extract_attachment_text, _extract_pdf_text, _get

SUPPORTED_EXTENSIONS = {".pdf", ".xlsx", ".xls"}
MAX_ATTACHMENTS_TO_PARSE = 4
MAX_CHARS_PER_FILE = 8000
MAX_TOTAL_CHARS = 14000
SHARES_ANNOUNCEMENT_KEYWORD = "Laporan Bulanan Registrasi Pemegang Efek"

SHARES_OUTSTANDING_KEYWORDS = [
    "shares outstanding",
    "total shares outstanding",
    "saham beredar",
    "jumlah saham beredar",
    "jumlah lembar saham beredar",
    "outstanding shares",
]
SHARES_FLOAT_KEYWORDS = [
    "shares float",
    "free float",
    "saham float",
    "saham publik",
    "float shares",
]
SHARES_INSTITUTIONAL_KEYWORDS = [
    "shares institutional",
    "institutional",
    "kepemilikan institusional",
    "saham institusional",
]
SHARES_INSIDER_KEYWORDS = [
    "shares insider",
    "insider",
    "kepemilikan insider",
    "saham insider",
    "manajemen dan insider",
]

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

NUMERIC_ROW_RE = re.compile(r"\d[\d,\.]*")


def _parse_idx_datetime(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()
    if not text:
        return None

    candidate_formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%d/%m/%Y %I:%M:%S %p",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%Y%m%d",
    ]

    iso_candidates = [text]
    if text.endswith("Z"):
        iso_candidates.append(text[:-1] + "+00:00")

    for candidate in iso_candidates:
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue

    for candidate_format in candidate_formats:
        try:
            parsed = datetime.strptime(text, candidate_format)
            if parsed.tzinfo is not None:
                parsed = parsed.replace(tzinfo=None)
            return parsed
        except ValueError:
            continue

    return None


def _format_report_date(value):
    parsed = _parse_idx_datetime(value)
    if not parsed:
        return None
    return parsed.date().isoformat()


def _normalize_announcement_reply(reply: dict) -> dict:
    pengumuman = reply.get("pengumuman") or {}
    attachments = reply.get("attachments") or reply.get("Attachments") or []
    title = str(pengumuman.get("JudulPengumuman") or "").strip()
    announcement_dt = _parse_idx_datetime(pengumuman.get("TglPengumuman") or pengumuman.get("CreatedDate"))

    return {
        "title": title,
        "date": announcement_dt,
        "month_key": announcement_dt.strftime("%Y-%m") if announcement_dt else None,
        "attachments": attachments,
        "raw": reply,
    }


def _select_monthly_announcements(replies: list[dict]) -> list[dict]:
    grouped = {}
    for reply in replies:
        normalized = _normalize_announcement_reply(reply)
        month_key = normalized.get("month_key")
        if not month_key:
            continue

        current = grouped.get(month_key)
        if current is None:
            grouped[month_key] = normalized
            continue

        current_title = str(current.get("title") or "").lower()
        candidate_title = str(normalized.get("title") or "").lower()
        current_is_correction = "koreksi" in current_title
        candidate_is_correction = "koreksi" in candidate_title

        if candidate_is_correction and not current_is_correction:
            grouped[month_key] = normalized
            continue

        if candidate_is_correction == current_is_correction:
            current_date = current.get("date")
            candidate_date = normalized.get("date")
            if candidate_date and (not current_date or candidate_date > current_date):
                grouped[month_key] = normalized

    return sorted(grouped.values(), key=lambda item: item.get("date") or datetime.min)


def _clean_numeric_value(value):
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    normalized = re.sub(r"[^\d]", "", text)
    if len(normalized) < 4:
        return None

    try:
        number = int(normalized)
    except ValueError:
        return None

    return number if number > 0 else None


def _normalize_share_report_text(text: str) -> str:
    normalized = str(text or "")
    normalized = re.sub(r"(?<=[.,])\s+(?=\d)", "", normalized)
    normalized = re.sub(r"(?<=\d)\s+(?=[.,]\d)", "", normalized)
    return normalized


def _extract_integer_values(text: str, include_zero: bool = False) -> list[int]:
    values = []
    for match in re.finditer(r"-|\d{1,3}(?:[.,]\d{3})+|\d+", text or ""):
        token = match.group(0)
        tail = text[match.end():match.end() + 3]
        if "%" in tail:
            continue
        if token == "-":
            if include_zero:
                values.append(0)
            continue

        cleaned = _clean_numeric_value(token)
        if cleaned is not None:
            values.append(cleaned)
        elif include_zero and re.fullmatch(r"0+", token):
            values.append(0)
    return values


def _extract_values_after_phrases(
    text: str,
    phrases: list[str],
    window: int = 400,
    include_zero: bool = False,
) -> list[int]:
    normalized = _normalize_share_report_text(text)
    lower_text = normalized.lower()

    for phrase in phrases:
        index = lower_text.find(phrase.lower())
        if index == -1:
            continue
        segment = normalized[index + len(phrase):index + len(phrase) + window]
        values = _extract_integer_values(segment, include_zero=include_zero)
        if values:
            return values

    return []


def _extract_first_after_phrases(
    text: str,
    phrases: list[str],
    window: int = 400,
    include_zero: bool = False,
) -> int | None:
    values = _extract_values_after_phrases(
        text,
        phrases,
        window=window,
        include_zero=include_zero,
    )
    return values[0] if values else None


def _extract_best_first_after_phrases(
    text: str,
    phrases: list[str],
    window: int = 400,
    include_zero: bool = False,
) -> int | None:
    normalized = _normalize_share_report_text(text)
    lower_text = normalized.lower()
    first_values = []

    for phrase in phrases:
        lower_phrase = phrase.lower()
        start = 0
        while True:
            index = lower_text.find(lower_phrase, start)
            if index == -1:
                break
            segment = normalized[index + len(phrase):index + len(phrase) + window]
            values = _extract_integer_values(segment, include_zero=include_zero)
            if values:
                first_values.append(values[0])
            start = index + len(phrase)

    return max(first_values) if first_values else None


def _extract_max_after_phrases(text: str, phrases: list[str], window: int = 400) -> int | None:
    values = _extract_values_after_phrases(text, phrases, window=window)
    return max(values) if values else None


def _extract_free_float_table_values(text: str) -> list[int]:
    return _extract_values_after_phrases(
        text,
        [
            "Jumlah saham Free Float",
            "The amount of Free Float Share",
        ],
        window=600,
        include_zero=True,
    )


def _extract_reported_free_float(text: str) -> int | None:
    values = _extract_free_float_table_values(text)
    if values:
        return values[0]

    values = _extract_values_after_phrases(
        text,
        [
            "Informasi Saham Free Float",
            "Free Float Share Information",
        ],
        window=500,
        include_zero=True,
    )
    if len(values) >= 2:
        return values[1]
    if values:
        return values[0]
    return None


def _extract_bod_boc_shares(text: str) -> int | None:
    normalized = _normalize_share_report_text(text)
    section_patterns = [
        (
            "Investor Type & Classification Number of Shares",
            "Number of Scripless Shares based on Investor Type and Classification from KSEI",
        ),
        (
            "Tipe dan Klasifikasi Investor Jumlah Saham",
            "Jumlah Saham Scripless berdasarkan Tipe dan Klasifikasi Investor dari KSEI",
        ),
    ]

    for start_marker, end_marker in section_patterns:
        start = normalized.find(start_marker)
        if start == -1:
            continue
        end = normalized.find(end_marker, start)
        if end == -1:
            continue

        section = normalized[start:end]
        if "BOD / BOC" not in section and "Direksi dan Dewan Komisaris" not in section:
            continue

        values = _extract_integer_values(section, include_zero=True)
        if len(values) >= 2:
            return values[1]

    return None


def _extract_director_commissioner_ownership(text: str) -> int | None:
    normalized = _normalize_share_report_text(text)
    section_markers = [
        "Laporan Kepemilikan Saham Oleh Direksi dan Komisaris",
        "Share Ownership Report by Directors and Commissioners",
    ]
    end_markers = [
        "Informasi Saham Free Float",
        "Free Float Share Information",
    ]

    for marker in section_markers:
        start = normalized.find(marker)
        if start == -1:
            continue

        end_candidates = [
            normalized.find(end_marker, start)
            for end_marker in end_markers
            if normalized.find(end_marker, start) != -1
        ]
        end = min(end_candidates) if end_candidates else start + 5000
        section = normalized[start:end]

        current_values = []
        for match in re.finditer(
            r"(\d{1,3}(?:[.,]\d{3})+)\s+\d+(?:[,.]\d+)?%\s+"
            r"(\d{1,3}(?:[.,]\d{3})+)\s+\d+(?:[,.]\d+)?%",
            section,
        ):
            cleaned = _clean_numeric_value(match.group(2))
            if cleaned is not None:
                current_values.append(cleaned)

        if current_values:
            return sum(current_values)

    return None


def _extract_free_float_bod_boc_shares(text: str) -> int | None:
    values = _extract_free_float_table_values(text)
    unique_values = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)

    if len(unique_values) >= 2:
        candidate = unique_values[1]
        if candidate < 1_000_000_000:
            return candidate
    return None


def _extract_shares_metrics_from_report(text: str) -> dict:
    shares_outstanding = _extract_max_after_phrases(
        text,
        ["Total"],
        window=160,
    )
    shares_float = _extract_reported_free_float(text)
    shares_institutional = _extract_best_first_after_phrases(
        text,
        ["Financial Institutional (IB)"],
        window=80,
        include_zero=True,
    )
    shares_insider = (
        _extract_bod_boc_shares(text)
        or _extract_director_commissioner_ownership(text)
        or _extract_free_float_bod_boc_shares(text)
    )

    return {
        "sharesOutstanding": shares_outstanding,
        "sharesFloat": shares_float,
        "sharesInstitutional": shares_institutional,
        "sharesInsider": shares_insider,
    }


def _extract_metric_from_text(lines: list[str], keywords: list[str]) -> int | None:
    lowered_lines = [line.lower() for line in lines]

    for index, lower_line in enumerate(lowered_lines):
        if not any(keyword in lower_line for keyword in keywords):
            continue

        same_line_matches = []
        for match in re.finditer(r"\d{1,3}(?:[.,]\d{3})+|\d+", lines[index]):
            cleaned = _clean_numeric_value(match.group(0))
            if cleaned is not None:
                same_line_matches.append(cleaned)
        if same_line_matches:
            return max(same_line_matches)

        search_window = "\n".join(lines[index:index + 4])
        numeric_matches = []
        for match in re.finditer(r"\d{1,3}(?:[.,]\d{3})+|\d+", search_window):
            cleaned = _clean_numeric_value(match.group(0))
            if cleaned is not None:
                numeric_matches.append(cleaned)

        if numeric_matches:
            return max(numeric_matches)

    return None


def _parse_shares_report_text(text: str, announcement_date: str | None = None) -> dict:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    report_metrics = _extract_shares_metrics_from_report(text)
    return {
        "date": announcement_date,
        "sharesOutstanding": report_metrics.get("sharesOutstanding") or _extract_metric_from_text(lines, SHARES_OUTSTANDING_KEYWORDS),
        "sharesFloat": report_metrics.get("sharesFloat") or _extract_metric_from_text(lines, SHARES_FLOAT_KEYWORDS),
        "sharesInstitutional": report_metrics.get("sharesInstitutional") or _extract_metric_from_text(lines, SHARES_INSTITUTIONAL_KEYWORDS),
        "sharesInsider": report_metrics.get("sharesInsider") or _extract_metric_from_text(lines, SHARES_INSIDER_KEYWORDS),
    }


def _fill_missing_share_metrics(items: list[dict]) -> list[dict]:
    carry_fields = ["sharesOutstanding", "sharesFloat", "sharesInsider"]

    for field in carry_fields:
        last_value = None
        for item in items:
            if item.get(field) is None:
                item[field] = last_value
            else:
                last_value = item.get(field)

        next_value = None
        for item in reversed(items):
            if item.get(field) is None:
                item[field] = next_value
            else:
                next_value = item.get(field)

    for item in items:
        if item.get("sharesInstitutional") is None:
            item["sharesInstitutional"] = 0

    return items


def fetch_idx_shares_announcements(symbol: str, date_from: str = "19010101", date_to: str | None = None) -> list[dict]:
    url = "https://www.idx.co.id/primary/ListedCompany/GetAnnouncement"
    params = {
        "kodeEmiten": symbol.upper(),
        "emitenType": "*",
        "indexFrom": 0,
        "pageSize": 100,
        "dateFrom": date_from,
        "dateTo": date_to or datetime.now().strftime("%Y%m%d"),
        "lang": "id",
        "keyword": SHARES_ANNOUNCEMENT_KEYWORD,
    }
    response = _get(url, params)
    replies = response.get("Replies") or response.get("Results") or []
    return replies if isinstance(replies, list) else []


def _get_announcement_full_save_path(reply: dict) -> str:
    attachments = reply.get("attachments") or reply.get("Attachments") or []
    for attachment in attachments:
        full_save_path = str(attachment.get("FullSavePath") or attachment.get("File_Path") or "").strip()
        if full_save_path.lower().endswith(".pdf"):
            return full_save_path
    first_attachment = attachments[0] if attachments else {}
    return str(first_attachment.get("FullSavePath") or first_attachment.get("File_Path") or "").strip()


def scrape_shares_data(symbol: str) -> dict:
    replies = fetch_idx_shares_announcements(symbol)
    selected_replies = _select_monthly_announcements(replies)

    items = []
    for reply in selected_replies:
        raw_reply = reply.get("raw") or {}
        pengumuman = raw_reply.get("pengumuman") or {}
        announcement_date = _format_report_date(pengumuman.get("TglPengumuman") or pengumuman.get("CreatedDate") or reply.get("date"))
        file_url = _get_announcement_full_save_path(raw_reply or reply)
        if not file_url:
            continue

        try:
            content = _download_file(file_url)
            extracted_text = _extract_pdf_text(content)
        except Exception:
            extracted_text = ""

        item = _parse_shares_report_text(extracted_text, announcement_date=announcement_date)
        if item.get("date") is None:
            item["date"] = announcement_date
        items.append(item)

    items.sort(key=lambda item: item.get("date") or "")
    _fill_missing_share_metrics(items)

    return {
        "symbol": symbol.upper(),
        "count": len(items),
        "items": items,
    }
