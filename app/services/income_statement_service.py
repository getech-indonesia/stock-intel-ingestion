from app.scrapers.income_statement import scrape_income_statement


def fetch_and_build_income_statement(symbol: str, year: int) -> dict:
    return scrape_income_statement(symbol, year)