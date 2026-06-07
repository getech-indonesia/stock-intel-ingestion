from __future__ import annotations

import re
from typing import Any

from app.scrapers.common import BASE_URL

SUPPORTED_EXTENSIONS = {".pdf", ".xlsx", ".xls"}
MAX_ATTACHMENTS_TO_PARSE = 20

NUMERIC_ALIASES = {
    "revenue": [
        "jumlahpendapatanoperasional",
        "totalpendapatanoperasional",
        "pendapatanoperasional",
        "pendapatanbungadansyariah",
        "jumlahpendapatanbungadansyariah",
        "interestandshariaincome",
        "totalinterestandshariaincome",
        "revenue",
        "pendapatan",
        "penjualan",
        "sales",
        "totalrevenue",
        "netsales",
    ],
    "cogs": ["cogs", "costofgoodsold", "costofsales", "costofrevenue", "bebanpokokpenjualan", "bebanpokok"],
    "grossProfit": ["grossprofit", "labakotor"],
    "operatingExpenses": ["operatingexpenses", "operatingexpense", "bebanoperasional", "bebanoperasi"],
    "sellingExpenses": ["sellingexpenses", "bebanpenjualan"],
    "generalAdminExpenses": ["generaladminexpenses", "generaladministrativeexpenses", "bebanumumdanadministrasi", "bebanadministrasi"],
    "rdExpenses": ["rdexpenses", "researchdevelopmentexpenses", "researchanddevelopment"],
    "depreciationAmort": ["depreciationamort", "depreciationandamortization", "depreciationamortization", "penyusutandanamortisasi"],
    "ebit": ["ebit", "earningbeforeinterestandtax"],
    "ebitda": ["ebitda"],
    "operatingIncome": [
        "operatingincome",
        "operatingprofit",
        "labaoperasional",
        "labaoperasi",
        "labausaha",
        "pendapatanbungadansyariahbersih",
        "pendapatanbungasyariahbersih",
        "netinterestandshariaincome",
    ],
    "interestExpense": ["interestexpense", "bebanbunga", "financecost"],
    "interestIncome": ["interestincome", "pendapatanbunga", "pendapatanbungadansyariah", "pendapatanbungasyariah"],
    "otherNonOperatingIncome": ["othernonoperatingincome", "otherincome", "nonoperatingincome", "pendapatanlainlain"],
    "pretaxIncome": ["pretaxincome", "profitbeforetax", "incomebeforetax", "labasebelumpajak"],
    "incomeTaxExpense": [
        "bebanpajakpenghasilan",
        "manfaatbebanpajakpenghasilan",
        "incometaxexpense",
        "taxexpense",
    ],
    "effectiveTaxRate": ["effectivetaxrate", "taxrate", "tarifpajakefektif"],
    "netIncome": ["netincome", "netprofit", "lababersih", "labaperiodeberjalan", "jumlahlaba"],
    "netIncomeAttributable": [
        "netincomeattributable",
        "attributabletoowners",
        "labaatribusikepadapemilikentitasinduk",
        "labarugiyangdapatdiatribusikankepadapemilikentitasinduk",
        "labayangdapatdiatribusikankepadapemilikentitasinduk",
        "lababersihyangdapatdiatribusikankepadapemilikentitasinduk",
    ],
    "minorityInterest": ["minorityinterest", "noncontrollinginterest", "kepentingannonpengendali"],
    "eps": ["eps", "earningpershare", "labapersahamdasar", "lababersihpersahamdasar"],
    "epsDiluted": ["epsdiluted", "dilutedeps", "labapersahamdilusian"],
    "sharesWeightedAvg": ["weightedaverageshares", "sharesweightedavg", "rataratasahamberedartertimbang"],
}

BALANCE_NUMERIC_ALIASES = {
    "cash": ["cash", "kasdansetarakas", "kas", "kasdanbank", "cashandcashequivalents"],
    "shortTermInvestments": [
        "shortterminvestments",
        "investasijangkapendek",
        "marketablesecurities",
        "penempatanpadabankindonesiadanbankbanklain",
        "giropadabankindonesia",
        "giropadabankbanklain",
        "efekefekyangdibeli",
    ],
    "accountsReceivable": ["accountsreceivable", "piutangusaha", "tradeandotherreceivables"],
    "inventory": ["inventory", "persediaan"],
    "otherCurrentAssets": ["othercurrentassets", "asetlancarlainnya", "asetlancarllain", "biayadibayardimuka", "pajakdibayardimuka", "asetlainlain"],
    "totalCurrentAssets": ["totalcurrentassets", "jumlahasetlancar", "asetlancar"],
    "propertyPlantEquipment": ["propertyplantequipment", "asettetap", "fixedassets"],
    "intangibleAssets": ["intangibleassets", "asettakberwujud", "asettidakberwujud"],
    "goodwill": ["goodwill"],
    "longTermInvestments": ["longterminvestments", "investasijangkapanjang"],
    "otherNonCurrentAssets": ["othernoncurrentassets", "asettidaklancarlainnya", "asetnonlancarlainnya"],
    "totalNonCurrentAssets": ["totalnoncurrentassets", "jumlahasettidaklancar", "asettidaklancar"],
    "totalAssets": ["totalassets", "jumlahaset", "totalaset"],
    "shortTermDebt": ["shorttermdebt", "utangjangkapendek", "pinjamanjangkapendek", "liabilitasjangkapendekberbunga"],
    "accountsPayable": ["accountspayable", "utangusaha", "tradepayables"],
    "deferredRevenue": ["deferredrevenue", "pendapatanditerimadimuka"],
    "otherCurrentLiabilities": ["othercurrentliabilities", "liabilitaslancarlainnya", "utanglancarlainnya"],
    "totalCurrentLiabilities": ["totalcurrentliabilities", "jumlahlibilitaslancar", "liabilitaslancar"],
    "longTermDebt": ["longtermdebt", "utangjangkapanjang", "pinjamanjangkapanjang", "liabilitasjangkapanjangberbunga"],
    "deferredTaxLiabilities": ["deferredtaxliabilities", "liabilitaspajaktangguhan"],
    "otherNonCurrentLiabilities": ["othernoncurrentliabilities", "liabilitasjangkapanjanglainnya", "liabilitasnonlancarlainnya"],
    "totalNonCurrentLiabilities": ["totalnoncurrentliabilities", "jumlahliabilitasjangkapanjang", "liabilitasnonlancar"],
    "totalLiabilities": ["totalliabilities", "jumlahliabilitas", "totalliabilitas"],
    "commonStock": ["commonstock", "modaldisetor", "modal saham", "issuedandfullypaidcapital"],
    "additionalPaidInCapital": ["additionalpaidincapital", "tambahanmodaldisetor", "agio"],
    "retainedEarnings": ["retainedearnings", "saldo laba", "labaditahan"],
    "treasuryStock": ["treasurystock", "sahamtreasury", "sahamdiperoleh kembali"],
    "otherEquity": ["otherequity", "ekuitaslainnya"],
    "minorityInterestEquity": ["minorityinterestequity", "kepentingannonpengendali", "noncontrollinginterest"],
    "totalEquity": ["totalequity", "jumlahekuitas", "totalekuitas"],
}

CASH_FLOW_NUMERIC_ALIASES = {
    "netIncomeStart": ["netincome", "profitfortheperiod", "profitfortheyear", "lababersih", "labaperiodiberjalan"],
    "depreciationAmort": ["depreciationamort", "depreciationandamortization", "depreciationamortization", "penyusutandanamortisasi"],
    "stockBasedCompensation": ["stockbasedcompensation", "sharebasedcompensation", "sharebasedpayment", "kompensasisaham", "pembayaranberbasissaham"],
    "changeInWorkingCapital": ["changeinworkingcapital", "changesinworkingcapital", "perubahanmodalkerja"],
    "changeInReceivables": ["changeinreceivables", "changesinreceivables", "changeintradeandotherreceivables", "perubahanpiutang"],
    "changeInInventory": ["changeininventory", "changesininventory", "perubahanpersediaan"],
    "changeInPayables": ["changeinpayables", "changesinpayables", "changeintradepayables", "perubahanutangusaha"],
    "otherOperatingActivities": ["otheroperatingactivities", "otheroperatingcashflows", "activitiessetelahtax", "aktivitasoperasilainnya"],
    "netCashFromOperations": [
        "netcashfromoperations",
        "netcashfromoperatingactivities",
        "netcashprovidedbyoperatingactivities",
        "aruskasbersihdariaktivitasoperasi",
        "kasbersihyangdiperolehdariaktivitasoperasi",
        "kasbersihdariaktivitasoperasi",
    ],
    "capitalExpenditures": [
        "capitalexpenditures",
        "capex",
        "purchaseofpropertyplantandequipment",
        "purchaseofppe",
        "pembelianaset tetap",
        "pembelianpropertyplantandequipment",
    ],
    "acquisitions": ["acquisitions", "acquisitionofsubsidiaries", "akuisisi"],
    "purchaseOfInvestments": ["purchaseofinvestments", "purchaseofmarketablesecurities", "pembelianinvestasi"],
    "saleOfInvestments": ["saleofinvestments", "proceedsfromsaleofinvestments", "penjualaninvestasi"],
    "otherInvestingActivities": ["otherinvestingactivities", "otherinvestingcashflows", "aktivitasinvestasilainnya"],
    "netCashFromInvesting": [
        "netcashfrominvesting",
        "netcashfrominvestingactivities",
        "netcashusedininvestingactivities",
        "aruskasbersihdariaktivitasinvestasi",
        "kasbersihyangdiperolehdariaktivitasinvestasi",
        "kasbersihyangdigunakanuntukaktivitasinvestasi",
    ],
    "debtIssuance": ["debtissuance", "proceedsfromdebt", "proceedsfromborrowings", "penerimaanpinjaman"],
    "debtRepayment": ["debtrepayment", "repaymentofdebt", "paymentofborrowings", "pelunasanpinjaman"],
    "commonStockIssuance": ["commonstockissuance", "issuanceofcommonstock", "proceedsfromissuanceofshares", "penerbitansaham"],
    "commonStockRepurchase": ["commonstockrepurchase", "repurchaseofcommonstock", "treasurystockpurchase", "pembeliankembalisaham"],
    "dividendsPaid": ["dividendspaid", "paymentofdividends", "dividendspaidtoshareholders", "dividendibayar"],
    "otherFinancingActivities": ["otherfinancingactivities", "otherfinancingcashflows", "aktivitaspendanaanlainnya"],
    "netCashFromFinancing": [
        "netcashfromfinancing",
        "netcashfromfinancingactivities",
        "netcashprovidedbyfinancingactivities",
        "aruskasbersihdariaktivitaspendanaan",
        "kasbersihyangdiperolehdariaktivitaspendanaan",
        "kasbersihyangdigunakanuntukaktivitaspendanaan",
    ],
    "netChangeInCash": [
        "netchangeincash",
        "netincreaseindcashandcashequivalents",
        "netincreasedecreaseincash",
        "perubahanbersihkas",
        "kenaikanpenurunanbersihkasdansetarakas",
    ],
    "cashBeginningPeriod": [
        "cashbeginningperiod",
        "cashandcashequivalentsatthebeginningoftheperiod",
        "cashatthebeginningoftheperiod",
        "kasawaltahun",
        "kasawalperiode",
        "kasdansetarakaspadawalperiode",
    ],
    "cashEndPeriod": [
        "cashendperiod",
        "cashandcashequivalentsattheendoftheperiod",
        "cashattheendoftheperiod",
        "kasakhirtahun",
        "kasakhirperiode",
        "kasdansetarakaspadaakhirperiode",
    ],
    "freeCashFlow": ["freecashflow", "freecashflowfcf", "fcf"],
}

FIELD_BLOCKED_TOKENS = {
    "incomeTaxExpense": ["sebelumpajak", "beforetax"],
}

TEXT_BLOCKLIST = [
    "komprehensif lain",
    "catatan",
    "note",
    "explanation",
    "penjelasan",
    "change in name",
]


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "".join(ch for ch in text if ch.isalnum())


def _normalize_file_extension(file_name: str, file_type: str | None = None) -> str:
    ext = str(file_type or "").strip().lower()
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    if ext in SUPPORTED_EXTENSIONS:
        return ext

    lower_name = str(file_name or "").lower()
    if "." in lower_name:
        guessed = f".{lower_name.rsplit('.', 1)[-1]}"
        if guessed in SUPPORTED_EXTENSIONS:
            return guessed
    return ""


def _to_number(value: Any):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    # Guard against narrative/text paragraphs being parsed as numbers.
    if len(text) > 64 and not re.search(r"\d", text):
        return None

    negative = text.startswith("(") and text.endswith(")")
    text = text.replace("(", "").replace(")", "")

    text = text.replace(" ", "")
    text = text.replace("Rp", "").replace("IDR", "").replace("idr", "")
    text = text.replace("USD", "").replace("usd", "")
    text = text.replace("%", "")

    multiplier = 1
    lower_text = text.lower()
    if "triliun" in lower_text:
        multiplier = 1_000_000_000_000
    elif "miliar" in lower_text:
        multiplier = 1_000_000_000
    elif "juta" in lower_text:
        multiplier = 1_000_000

    text = re.sub(r"[^0-9,.-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None

    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(",") > 1 and "." not in text:
        text = text.replace(",", "")
    elif text.count(".") > 1 and "," not in text:
        text = text.replace(".", "")
    elif "," in text:
        tail = text.split(",")[-1]
        if len(tail) == 3 and text.replace(",", "").replace("-", "").isdigit():
            text = text.replace(",", "")
        else:
            text = text.replace(",", ".")

    try:
        number = float(text) * multiplier
    except ValueError:
        return None

    if negative:
        number = -number

    return number


def _detect_unit_multiplier(rows: list[list[Any]]) -> float:
    for row in rows[:100]:
        for cell in row[:20]:
            text = str(cell or "").strip().lower()
            if not text:
                continue
            if "dalam jutaan" in text:
                return 1_000_000.0
            if "dalam miliaran" in text or "dalam miliar" in text:
                return 1_000_000_000.0
            if "dalam ribuan" in text:
                return 1_000.0
            if "dalam triliunan" in text or "dalam triliun" in text:
                return 1_000_000_000_000.0
            if "million" in text and "rupiah" in text:
                return 1_000_000.0
            if "billion" in text and "rupiah" in text:
                return 1_000_000_000.0
    return 1.0


def _to_ratio(value: Any):
    number = _to_number(value)
    if number is None:
        return None
    if abs(number) > 1:
        return round(number / 100.0, 6)
    return round(number, 6)


def _attachment_url(attachment: dict) -> str:
    file_path = str(attachment.get("File_Path") or attachment.get("file_path") or "").strip()
    if not file_path:
        return ""
    if file_path.startswith("http"):
        return file_path
    return f"{BASE_URL}{file_path}"


def _score_attachment(attachment: dict) -> int:
    file_name = str(attachment.get("File_Name") or attachment.get("file_name") or "").lower()
    score = 0
    for keyword in [
        "laporankeuangan",
        "laporan keuangan",
        "lapkeu",
        "lap keu",
        "laporan keuangan konsolidasian",
        "laba rugi",
        "income statement",
        "bod statement",
    ]:
        if keyword in file_name:
            score += 4
    if re.search(r"(?:^|[\s\-_])fs(?:[\s\-_]|$)", file_name):
        score += 3
    if "pdf" in file_name:
        score += 2
    if file_name.endswith(".xlsx"):
        score += 2
    if file_name.endswith(".xls"):
        score += 1
    if "xbrl" in file_name:
        score += 1
    return score


def _is_spreadsheet_attachment(attachment: dict) -> bool:
    file_name = str(attachment.get("File_Name") or attachment.get("file_name") or "")
    file_type = str(attachment.get("File_Type") or attachment.get("file_type") or "")
    ext = _normalize_file_extension(file_name, file_type)
    return ext in SUPPORTED_EXTENSIONS


def _extract_currency(rows: list[list[Any]]):
    for row in rows[:30]:
        for cell in row[:6]:
            text = str(cell or "").strip().lower()
            if not text:
                continue
            if "idr" in text or "rupiah" in text:
                return "IDR"
            if "usd" in text or "dollar" in text:
                return "USD"
    return None


def _normalize_text_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = " ".join(str(raw_line).replace("\u00a0", " ").split())
        if line:
            lines.append(line)
    return lines


def _text_to_rows(text: str) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for raw_line in str(text or "").splitlines():
        line = str(raw_line).replace("\u00a0", " ").strip()
        if not line:
            continue
        cells = [part.strip() for part in re.split(r"\t+|\s{2,}", line) if part.strip()]
        rows.append(cells or [line])
    return rows


def _looks_like_balance_heading(line: str) -> bool:
    lower = line.lower()
    return any(
        keyword in lower
        for keyword in [
            "laporan posisi keuangan",
            "financial position",
            "statements of financial position",
        ]
    )


def _looks_like_income_heading(line: str) -> bool:
    lower = line.lower()
    return any(
        keyword in lower
        for keyword in [
            "laporan laba rugi",
            "profit or loss",
            "income and other comprehensive income",
            "penghasilan komprehensif",
        ]
    )


def _looks_like_cash_flow_heading(line: str) -> bool:
    lower = line.lower()
    return any(keyword in lower for keyword in ["laporan arus kas", "cash flows"])


def _looks_like_equity_heading(line: str) -> bool:
    lower = line.lower()
    return any(keyword in lower for keyword in ["laporan perubahan ekuitas", "changes in equity"])


def _split_pdf_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"balance": [], "income": [], "cash_flow": []}
    current_section: str | None = None

    for raw_line in str(text or "").splitlines():
        line = str(raw_line).replace("\u00a0", " ").strip()
        if not line:
            continue
        normalized = " ".join(line.split())

        if _looks_like_equity_heading(normalized):
            current_section = None
            continue
        if _looks_like_balance_heading(normalized):
            current_section = "balance"
            continue
        if _looks_like_income_heading(normalized):
            current_section = "income"
            continue
        if _looks_like_cash_flow_heading(normalized):
            current_section = "cash_flow"
            continue

        if current_section:
            sections[current_section].append(line)

    full_text = "\n".join(str(raw_line).replace("\u00a0", " ").strip() for raw_line in str(text or "").splitlines() if str(raw_line).strip())
    return {
        "balance": "\n".join(sections["balance"]) or full_text,
        "income": "\n".join(sections["income"]) or full_text,
        "cash_flow": "\n".join(sections["cash_flow"]) or full_text,
    }


def _normalize_period(result: dict) -> str:
    raw = str(result.get("Report_Period") or result.get("report_period") or "").strip().lower()
    if "audit" in raw or "annual" in raw or "tahunan" in raw:
        return "AUDIT"
    if any(token in raw for token in ["q1", "tw1", "triwulan i", "triwulan 1"]):
        return "Q1"
    if any(token in raw for token in ["q2", "tw2", "triwulan ii", "triwulan 2"]):
        return "Q2"
    if any(token in raw for token in ["q3", "tw3", "triwulan iii", "triwulan 3"]):
        return "Q3"
    if any(token in raw for token in ["q4", "tw4", "triwulan iv", "triwulan 4"]):
        return "Q4"
    return "AUDIT"


def _period_from_file_name(file_name: str) -> str | None:
    lower_name = (file_name or "").lower()
    if not lower_name:
        return None

    if any(token in lower_name for token in ["tahunan", "annual", "audit"]):
        return "AUDIT"

    if re.search(r"(?:^|[-_\s])iv(?:[-_\s.]|$)", lower_name):
        return "Q4"
    if re.search(r"(?:^|[-_\s])iii(?:[-_\s.]|$)", lower_name):
        return "Q3"
    if re.search(r"(?:^|[-_\s])ii(?:[-_\s.]|$)", lower_name):
        return "Q2"
    if re.search(r"(?:^|[-_\s])i(?:[-_\s.]|$)", lower_name):
        return "Q1"

    if any(token in lower_name for token in ["q1", "tw1", "triwulan1", "quarter1"]):
        return "Q1"
    if any(token in lower_name for token in ["q2", "tw2", "triwulan2", "quarter2"]):
        return "Q2"
    if any(token in lower_name for token in ["q3", "tw3", "triwulan3", "quarter3"]):
        return "Q3"
    if any(token in lower_name for token in ["q4", "tw4", "triwulan4", "quarter4"]):
        return "Q4"

    return None


def _resolve_period(result: dict, file_name: str) -> str:
    by_file_name = _period_from_file_name(file_name)
    if by_file_name:
        return by_file_name
    raw = str(result.get("Report_Period") or result.get("report_period") or "").strip().lower()
    if "audit" in raw or "annual" in raw or "tahunan" in raw:
        return "AUDIT"
    if any(token in raw for token in ["q1", "tw1", "triwulan i", "triwulan 1"]):
        return "Q1"
    if any(token in raw for token in ["q2", "tw2", "triwulan ii", "triwulan 2"]):
        return "Q2"
    if any(token in raw for token in ["q3", "tw3", "triwulan iii", "triwulan 3"]):
        return "Q3"
    if any(token in raw for token in ["q4", "tw4", "triwulan iv", "triwulan 4"]):
        return "Q4"
    return "AUDIT"


def _fiscal_quarter(period: str):
    mapping = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
    return mapping.get(period)


def _period_end_date(fiscal_year: int, fiscal_quarter: int | None) -> str:
    if fiscal_quarter == 1:
        return f"{fiscal_year}-03-31"
    if fiscal_quarter == 2:
        return f"{fiscal_year}-06-30"
    if fiscal_quarter == 3:
        return f"{fiscal_year}-09-30"
    return f"{fiscal_year}-12-31"


def _audit_status(period: str) -> str:
    if period == "AUDIT":
        return "AUDITED"
    return "UNAUDITED"
