
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.scrapers.common import BASE_URL, _get
from app.scrapers.fs_utilities.fs_collectors import fetch_financial_report_results
from app.scrapers.financial_statement_v2 import _filter_attachments, scrape_financial_statement_v2

print("=== Testing Financial Statement V2 ===")
symbol = "BBCA"
year = 2024  # Let's try 2024 first since 2025 might not have data yet
sector = "keuangan"

print(f"\n1. Testing fetch_financial_report_results for {symbol} {year}...")
try:
    results = fetch_financial_report_results(symbol, year)
    print(f"   ✓ Got {len(results)} results")
    for i, res in enumerate(results[:3]):
        print(f"   Result {i+1}: Report_Period={res.get('Report_Period')}, Report_Year={res.get('Report_Year')}")
        if 'Attachments' in res:
            print(f"   Attachments count: {len(res['Attachments'])}")
            for j, att in enumerate(res['Attachments'][:3]):
                print(f"     Attachment {j+1}: File_Name={att.get('File_Name')}, File_Type={att.get('File_Type')}")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print(f"\n2. Testing scrape_financial_statement_v2...")
try:
    data = scrape_financial_statement_v2(symbol, year, sector)
    print(f"   ✓ Got {len(data)} items")
    for item in data:
        print(f"   - {item['period']} {item['fiscalYear']}: Revenue={item['revenue']}, Net Income={item['netIncome']}")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Done ===")
