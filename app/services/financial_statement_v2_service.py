from app.scrapers.financial_statement_v2 import scrape_financial_statement_v2


def fetch_and_build_financial_statement_v2(symbol: str, year: int, sector: str | None = None):
    """Fetch and build financial statement v2 data"""
    results = scrape_financial_statement_v2(symbol, year, sector)
    return {
        "income_statement": {
            "counts": len(results),
            "items": results
        }
    }
