from app.scrapers.stockbit_income_statement import scrape_stockbit_income_statement


def fetch_and_build_income_statement(symbol: str) -> dict:
    return scrape_stockbit_income_statement(symbol)
