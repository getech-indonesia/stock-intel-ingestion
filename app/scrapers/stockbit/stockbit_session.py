from typing import Any
import time
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .config import SESSION_EXPIRED_MODAL, SESSION_EXPIRED_TITLE


class StockbitSessionHandler:
    """Handler untuk manage session Stockbit dan popup"""
    
    def __init__(self, page: Any):
        self.page = page
    
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
        print(f"\n⚠️  SESSION EXPIRED - Silakan login manual di browser")
        print(f"   Anda punya {timeout} detik ({timeout//60} menit) untuk login...")
        print(f"   Setelah login berhasil, scraping akan lanjut otomatis\n")
        
        start_time = time.time()
        check_interval = 2
        
        while time.time() - start_time < timeout:
            if not self.check_session_expired():
                print("✓ Login berhasil detected! Popup hilang...")
                time.sleep(2)  # Wait halaman stabilize
                return True
            
            elapsed = int(time.time() - start_time)
            remaining = timeout - elapsed
            if elapsed % 10 == 0:
                print(f"   ⏳ Menunggu login... ({remaining}s remaining)")
            
            time.sleep(check_interval)
        
        print(f"✗ Timeout: User tidak login dalam {timeout} detik")
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