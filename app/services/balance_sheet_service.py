from app.scrapers.stockbit.stockbit_balance_sheet import scrape_balance_sheet

def fetch_and_build_balance_sheet(symbol: str) -> dict:
    return scrape_balance_sheet(symbol)
