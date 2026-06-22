import logging

from app.scrapers.stockbit.stockbit_income_statement import scrape_stockbit_income_statement


logger = logging.getLogger(__name__)


def fetch_and_build_income_statement(symbol: str) -> dict:
    symbol = str(symbol).strip().upper()

    try:
        result = scrape_stockbit_income_statement(symbol)
    except Exception:
        print(f"[ERROR] Income statement scrape failed for symbol {symbol}", flush=True)
        logger.exception("Income statement scrape failed for symbol %s", symbol)
        raise

    data = result.get("data") if isinstance(result, dict) else None
    if not data:
        print(f"[WARN] Income statement scrape returned empty data for symbol {symbol}", flush=True)
        logger.warning("Income statement scrape returned empty data for symbol %s", symbol)

    return result
