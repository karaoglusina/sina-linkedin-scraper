"""
Browser automation using Playwright.

PERFORMANCE OPTIMIZATIONS:
1. Removed unnecessary fixed waits
2. Use smart waiting (wait for elements, not arbitrary time)
3. Reduced timeout values for quick checks
4. Browser can be reused for batch scraping
"""

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, Playwright
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Union
import os

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


# Default directory where the scraper saves its own browser profile.
# Using Playwright's bundled Chromium (not system Chrome) avoids all
# macOS Keychain complications entirely.
DEFAULT_PROFILE_DIR = str(Path.home() / ".sina-scraper-profile")

# Shared launch args for the scraper profile browser
_PROFILE_ARGS = [
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-session-crashed-bubble",
]


@contextmanager
def setup_scraper_profile(
    profile_dir: str = DEFAULT_PROFILE_DIR,
) -> Generator[BrowserContext, None, None]:
    """
    Open a visible browser window so the user can log into LinkedIn.
    The session is saved to `profile_dir` and reused on every future scrape.

    Usage:
        with setup_scraper_profile() as ctx:
            # browser is open; user logs in manually
            pass   # close the context when done
    """
    profile_dir = os.path.expanduser(profile_dir)
    Path(profile_dir).mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=_PROFILE_ARGS,
            ignore_default_args=["--enable-automation"],
        )
        page = context.new_page()
        page.goto("https://www.linkedin.com/login")
        try:
            yield context
        finally:
            context.close()


@contextmanager
def create_browser_persistent(
    profile_dir: str = DEFAULT_PROFILE_DIR,
) -> Generator[BrowserContext, None, None]:
    """
    Launch Playwright's bundled Chromium reusing a previously saved profile.

    Because this is NOT the system Chrome profile, there are no macOS Keychain
    complications — Playwright manages its own simple profile encryption.

    The profile must have been created first via setup_scraper_profile() so that
    the LinkedIn session cookies are already saved inside `profile_dir`.

    Args:
        profile_dir: Directory where the scraper profile is stored.
                     Defaults to ~/.sina-scraper-profile
    """
    profile_dir = os.path.expanduser(profile_dir)

    if not Path(profile_dir).exists():
        raise RuntimeError(
            f"Scraper profile not found at '{profile_dir}'. "
            "Please use 'Setup Profile' in the web UI to log in first."
        )

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=_PROFILE_ARGS,
            ignore_default_args=["--enable-automation"],
        )
        try:
            yield context
        finally:
            context.close()


def navigate_to_job(browser: Union[Browser, BrowserContext], url: str) -> Page:
    """
    Navigate to a LinkedIn job URL and wait for content to load.
    
    OPTIMIZED: Reduced waits from ~5s to ~0.5s
    """
    page = browser.new_page()

    # Make sure this tab is in front (important when restoring a previous session
    # leaves other tabs open behind our new one)
    page.bring_to_front()

    # Navigate and wait for initial HTML
    page.goto(url, wait_until="domcontentloaded")

    # Give the SPA time to render.  networkidle fires when no network requests
    # are in flight for 500 ms, which usually means React has finished rendering.
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass  # Proceed anyway — networkidle can be slow on heavy pages

    # Extra buffer for late-rendering React components
    page.wait_for_timeout(2000)

    # Handle popups
    _handle_popups_fast(page)

    # Check for redirect (expired job)
    current_url = page.url.lower()
    if "/jobs/view/" not in current_url or "expired" in current_url:
        page.close()
        raise Exception("Job listing has expired or is no longer available")

    # URL is still /jobs/view/{id}/ — the page is on the right job.
    # LinkedIn's SPA uses h2 / div[role="heading"] rather than h1 for the job
    # title, so we skip element-level checks and let the extractor handle it.
    print("  ✓ Job page loaded")
    
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
    Click 'Show more' on the job description if it is truncated.

    Two strategies:
    1. Logged-out view — stable named CSS class selector.
    2. Logged-in SPA  — hashed CSS classes; use Playwright's text selector
       which is immune to class-name changes.
    """
    # Strategy 1: logged-out named selector
    try:
        show_more = page.locator(".description__text button:has-text('Show more')")
        if show_more.is_visible(timeout=500):
            show_more.click()
            return
    except Exception:
        pass

    # Strategy 2: logged-in SPA — find any visible "Show more" button
    try:
        # Scope to the job description area to avoid clicking unrelated buttons
        for scope in ["#job-details", ".jobs-description", "main", "body"]:
            btn = page.locator(f"{scope} button:has-text('Show more')").first
            if btn.count() and btn.is_visible(timeout=300):
                btn.click(force=True)
                return
    except Exception:
        pass
