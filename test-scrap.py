from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=False)
    page = browser.new_page()
    page.goto("https://stockbit.com/symbol/BBCA/financials", timeout=60000)
    page.wait_for_timeout(5000)
    print(page.title())
    print(page.url)
    page.screenshot(path="debug.png", full_page=True)
    browser.pause()  # ini buka Playwright Inspector, bisa lihat & klik manual
    browser.close()