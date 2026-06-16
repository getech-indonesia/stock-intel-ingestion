from pathlib import Path
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


from typing import Optional

def _find_browser_executable() -> Optional[str]:
    for executable in BROWSER_EXECUTABLES:
        if executable.exists():
            return str(executable)
    return None

profile = Path('playwright_user_data')
profile.mkdir(exist_ok=True)

with sync_playwright() as p:
    try:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
    except Exception as e:
        print('Failed to launch persistent context with channel="chrome":', e)
        executable_path = _find_browser_executable()
        if executable_path:
            print('Falling back to a persistent context with an explicit browser executable.')
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile),
                    executable_path=executable_path,
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"],
                )
            except Exception as e2:
                print('Failed to launch persistent context with executable_path:', e2)
                context = None
        else:
            context = None

        if context is None:
            print('Falling back to default chromium launch (may open Chrome for Testing).')
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
                ignore_default_args=["--enable-automation"],
            )
            page = browser.new_page()
            page.goto('https://stockbit.com/login')
            print('Please complete login in the opened browser. Close the window when done.')
            browser.wait_for_event('disconnected')
        else:
                page = context.new_page()
            page.goto('https://stockbit.com/login')
            print('Please complete login in the opened browser. Close the window when done.')
            context.wait_for_event('close')
    else:
        else:
            page = context.new_page()
        page.goto('https://stockbit.com/login')
        print('Please complete login in the opened browser. Close the window when done.')
        context.wait_for_event('close')

print('Manual login helper finished. The profile is stored in playwright_user_data')
