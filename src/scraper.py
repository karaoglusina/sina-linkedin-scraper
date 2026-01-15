"""
Browser automation using Playwright.

PERFORMANCE OPTIMIZATIONS:
1. Removed unnecessary fixed waits
2. Use smart waiting (wait for elements, not arbitrary time)
3. Reduced timeout values for quick checks
4. Browser can be reused for batch scraping
"""

from playwright.sync_api import sync_playwright, Page, Browser, Playwright
from contextlib import contextmanager
from typing import Generator, Optional

# Global playwright instance for browser reuse
_playwright_instance: Optional[Playwright] = None
_browser_instance: Optional[Browser] = None


def get_browser(headless: bool = True) -> Browser:
    """
    Get or create a browser instance (singleton pattern).
    
    PERFORMANCE: Reusing browser saves ~2 seconds per scrape.
    Call close_browser() when done with all scraping.
    """
    global _playwright_instance, _browser_instance
    
    if _browser_instance is None or not _browser_instance.is_connected():
        if _playwright_instance is None:
            _playwright_instance = sync_playwright().start()
        _browser_instance = _playwright_instance.chromium.launch(headless=headless)
    
    return _browser_instance


def close_browser() -> None:
    """Close the browser and playwright instances."""
    global _playwright_instance, _browser_instance
    
    if _browser_instance:
        _browser_instance.close()
        _browser_instance = None
    
    if _playwright_instance:
        _playwright_instance.stop()
        _playwright_instance = None


@contextmanager
def create_browser(headless: bool = True) -> Generator[Browser, None, None]:
    """
    Context manager for browser lifecycle (single-use).
    
    For single scrapes or when you want automatic cleanup.
    For batch scraping, use get_browser() instead.
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            yield browser
        finally:
            browser.close()


def navigate_to_job(browser: Browser, url: str) -> Page:
    """
    Navigate to a LinkedIn job URL and wait for content to load.
    
    OPTIMIZED: Reduced waits from ~5s to ~0.5s
    """
    page = browser.new_page()
    
    # Navigate - domcontentloaded is faster than load
    page.goto(url, wait_until="domcontentloaded")
    
    # Handle popups quickly (in parallel conceptually)
    _handle_popups_fast(page)
    
    # Check for redirect (expired job)
    # LinkedIn redirects expired jobs to search pages with ?trk=expired_jd_redirect
    # or removes /view/ from the URL
    current_url = page.url.lower()
    if "/jobs/view/" not in current_url or "expired" in current_url:
        page.close()
        raise Exception("Job listing has expired or is no longer available")
    
    # Wait for the job title - must be in the job card, not a generic h1
    try:
        # Use specific job title selectors (not generic h1 which matches search pages)
        page.wait_for_selector(".top-card-layout__title, .topcard__title", timeout=10000)
        print("  ✓ Job title found")
    except Exception as e:
        page.close()
        raise Exception(f"Could not find job content - page may have changed or job expired: {e}")
    
    # Expand description if truncated
    _expand_description(page)
    
    return page


def _handle_popups_fast(page: Page) -> None:
    """
    Quickly dismiss cookie banner and login popup.
    
    IMPORTANT: LinkedIn shows a login modal that BLOCKS the cookie button.
    We must dismiss the modal FIRST, then accept cookies.
    
    OPTIMIZED: 
    - Press Escape first to dismiss modal overlay
    - Use force=True for cookie click to avoid overlay issues
    - Very short timeouts
    """
    # FIRST: Dismiss any modal overlay (login popup)
    try:
        page.keyboard.press("Escape")
    except:
        pass
    
    # THEN: Try to accept cookies (use force=True to bypass any remaining overlay)
    try:
        for selector in [
            'button:has-text("Accept")',
            'button:has-text("Accepteren")',
        ]:
            button = page.locator(selector).first
            if button.is_visible(timeout=300):
                button.click(force=True, timeout=1000)  # force=True bypasses overlay
                print("  ✓ Accepted cookies")
                break
    except:
        pass  # Cookie banner might not exist - that's fine
    
    print("  ✓ Dismissed popups")


def _expand_description(page: Page) -> None:
    """
    Click "Show more" button if present.
    
    OPTIMIZED: No arbitrary wait after click
    """
    try:
        show_more = page.locator(".description__text button:has-text('Show more')")
        if show_more.is_visible(timeout=500):
            show_more.click()
    except:
        pass
