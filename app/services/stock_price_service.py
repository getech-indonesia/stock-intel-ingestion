from app.scrapers.stock_price import fetch_idx_stock_price


def fetch_and_build_stock_price(symbol: str) -> dict:
    return fetch_idx_stock_price(symbol)