from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright


CHROME_EXECUTABLES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
]

BRAVE_EXECUTABLES = [
    Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
    Path(r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"),
]

BROWSER_EXECUTABLES = CHROME_EXECUTABLES + BRAVE_EXECUTABLES


def _find_browser_executable() -> Optional[str]:
    for executable in BROWSER_EXECUTABLES:
        if executable.exists():
            return str(executable)
    return None


def open_chromium():
    profile_dir = Path("playwright_user_data")
    profile_dir.mkdir(exist_ok=True)

    playwright = sync_playwright().start()
    executable_path = _find_browser_executable()

    context_args = {
        "user_data_dir": str(profile_dir),
        "headless": False,
        "args": [
            "--start-maximized",
            "--window-size=1920,1080",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
        "ignore_default_args": ["--enable-automation"],
        "no_viewport": True,
    }

    if executable_path:
        context_args["executable_path"] = executable_path

    context = playwright.chromium.launch_persistent_context(**context_args)
    context.set_default_timeout(0)
    context.set_default_navigation_timeout(0)
    page = context.pages[0] if context.pages else context.new_page()
    page.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['id-ID', 'id', 'en-US', 'en']
        });
        window.chrome = { runtime: {} };
        """
    )

    page.goto("https://stockbit.com/login", wait_until="domcontentloaded", timeout=0)
    print("Chromium opened with persistent profile at playwright_user_data")
    print("Close the browser window to end this script.")
    context.wait_for_event("close")


if __name__ == "__main__":
    open_chromium()
