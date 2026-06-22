import logging

from app.scrapers.stockbit.stockbit_balance_sheet import scrape_balance_sheet


logger = logging.getLogger(__name__)


def fetch_and_build_balance_sheet(symbol: str) -> dict:
    symbol = str(symbol).strip().upper()

    try:
        result = scrape_balance_sheet(symbol)
    except Exception:
        print(f"[ERROR] Balance sheet scrape failed for symbol {symbol}", flush=True)
        logger.exception("Balance sheet scrape failed for symbol %s", symbol)
        raise

    data = result.get("data") if isinstance(result, dict) else None
    if not data:
        print(f"[WARN] Balance sheet scrape returned empty data for symbol {symbol}", flush=True)
        logger.warning("Balance sheet scrape returned empty data for symbol %s", symbol)

    return result
