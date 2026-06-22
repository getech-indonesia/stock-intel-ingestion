from typing import Any
import time
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .config import SESSION_EXPIRED_MODAL, SESSION_EXPIRED_TITLE


class StockbitSessionHandler:
    """Handler untuk manage session Stockbit dan popup"""

    def __init__(self, page: Any):
        self.page = page

    def is_login_page(self) -> bool:
        """Cek apakah browser sedang berada di halaman login Stockbit."""
        try:
            current_url = (self.page.url or "").lower()
            if "stockbit.com/login" in current_url or current_url.endswith("/login"):
                return True
            if "/login" in current_url and "stockbit.com" in current_url:
                return True
            return False
        except:
            return False

    def check_session_expired(self) -> bool:
        """Cek apakah popup session expired muncul"""
        try:
            modal = self.page.locator(SESSION_EXPIRED_MODAL)
            if modal.count() > 0:
                title = self.page.locator(SESSION_EXPIRED_TITLE)
                if title.count() > 0:
                    return True
            return False
        except:
            return False

    def wait_for_manual_login(self, timeout: int = 300) -> bool:
        """
        Tunggu user login manual
        timeout: dalam detik (default 5 menit)
        """
        print("\n[LOGIN] Stockbit minta login manual di browser.")
        print(f"[LOGIN] Waktu tunggu: {timeout} detik ({timeout // 60} menit).")
        print("[LOGIN] Setelah login berhasil, scraper akan retry otomatis.\n")

        start_time = time.time()
        check_interval = 2

        while time.time() - start_time < timeout:
            if not self.is_login_page() and not self.check_session_expired():
                print("[LOGIN] Login berhasil terdeteksi, lanjut scraping...")
                time.sleep(2)
                return True

            elapsed = int(time.time() - start_time)
            remaining = timeout - elapsed
            if elapsed % 10 == 0:
                print(f"[LOGIN] Menunggu login... ({remaining}s tersisa)")

            time.sleep(check_interval)

        print(f"[LOGIN] Timeout: user tidak login dalam {timeout} detik")
        return False

    def handle_session_with_retry(self, max_retries: int = 3) -> bool:
        """Handle session timeout dengan retry mechanism"""
        retry_count = 0

        while retry_count < max_retries:
            if not self.check_session_expired():
                return True

            retry_count += 1
            print(f"\n[Retry {retry_count}/{max_retries}] Session expired detected")

            if not self.wait_for_manual_login(timeout=300):
                return False

        return False

    def wait_for_element_with_session_check(
        self,
        selector: str,
        timeout: int = 30000,
        state: str = "visible"
    ):
        """
        Wait for element dengan session check
        Akan retry jika session expired muncul
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

        try:
            self.page.wait_for_selector(selector, timeout=timeout, state=state)
            return True
        except PlaywrightTimeoutError:
            if self.check_session_expired():
                print("   Session expired saat wait element, menunggu login...")
                if self.handle_session_with_retry(max_retries=2):
                    # Retry wait setelah login
                    try:
                        self.page.wait_for_selector(selector, timeout=timeout, state=state)
                        return True
                    except PlaywrightTimeoutError:
                        return False
            return False
