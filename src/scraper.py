from playwright.sync_api import sync_playwright, Page, Browser
from contextlib import contextmanager
from typing import Generator


@contextmanager
def create_browser(headless: bool = True) -> Generator[Browser, None, None]:
    """
    Context manager for browser lifecycle.
    
    Usage:
        with create_browser() as browser:
            page = browser.new_page()
            # ... do stuff
        # Browser automatically closes here
    
    Args:
        headless: If True, browser runs invisibly. Set False for debugging.
    """
    with sync_playwright() as playwright:
        # Launch Chromium browser
        # Other options: playwright.firefox, playwright.webkit
        browser = playwright.chromium.launch(headless=headless)
        try:
            yield browser
        finally:
            browser.close()


def navigate_to_job(browser: Browser, url: str) -> Page:
    """
    Navigate to a LinkedIn job URL and wait for content to load.
    
    KEY CONCEPT: Waiting Strategy
    - We can't just navigate and immediately scrape
    - JavaScript needs time to fetch and render data
    - We wait for specific elements that indicate the page is ready
    
    Args:
        browser: Playwright browser instance
        url: LinkedIn job posting URL
        
    Returns:
        Page object ready for data extraction
    """
    # Create a new page (like opening a new tab)
    page = browser.new_page()
    
    # Navigate to the URL
    # Playwright waits for the initial load automatically
    page.goto(url, wait_until="domcontentloaded")
    
    # Handle cookie consent banner if present
    _handle_cookie_consent(page)
    
    # Dismiss login popup if present
    _dismiss_login_popup(page)
    
    # Check if job has expired (redirected to search page)
    # But not if we're still on a /jobs/view/ page
    if "/jobs/view/" not in page.url and ("/jobs/search" in page.url or "expired" in page.url):
        raise Exception("Job listing has expired or is no longer available")
    
    # Wait for the job title to be present (most reliable element)
    # This is our signal that the page has fully rendered
    try:
        page.wait_for_selector(".top-card-layout__title, .topcard__title, h1", timeout=10000)
        print("  ✓ Job title found")
    except Exception as e:
        raise Exception(f"Could not find job content. The page may have changed or the job expired. Error: {e}")
    
    # Wait a bit more for all content to load
    page.wait_for_timeout(1000)
    
    # Handle "Show more" button if present
    # Some descriptions are truncated and need expansion
    _expand_description(page)
    
    return page


def _handle_cookie_consent(page: Page) -> None:
    """
    Dismiss cookie consent banner if present.
    
    LinkedIn shows a cookie consent popup that can block interaction.
    We need to accept or dismiss it to proceed.
    """
    try:
        # Wait a moment for the page to settle
        page.wait_for_timeout(1000)
        
        # Look for common cookie consent buttons
        # LinkedIn uses different text in different languages
        consent_buttons = [
            'button:has-text("Accepteren")',  # Dutch
            'button:has-text("Accept")',      # English
            'button:has-text("Akzeptieren")', # German
            'button:has-text("Accepter")',    # French
            '[data-tracking-control-name="ga-cookie.consent.accept.v4"]',
        ]
        
        for selector in consent_buttons:
            try:
                button = page.locator(selector).first
                if button.is_visible(timeout=1000):
                    button.click()
                    print("  ✓ Accepted cookies")
                    page.wait_for_timeout(500)
                    return
            except:
                continue
    except Exception:
        # Cookie banner might not be present - that's fine
        pass


def _dismiss_login_popup(page: Page) -> None:
    """
    Dismiss the login/signup popup that LinkedIn shows.
    
    LinkedIn shows a modal asking users to sign in.
    Pressing Escape or clicking outside dismisses it.
    """
    try:
        # Wait a moment for any popup to appear
        page.wait_for_timeout(1000)
        
        # Try pressing Escape multiple times to dismiss any popups
        for _ in range(3):
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
        
        print("  ✓ Dismissed popups")
        
    except Exception:
        # Modal might not be present - that's fine
        pass


def _expand_description(page: Page) -> None:
    """
    Click "Show more" button to expand truncated job descriptions.
    
    LinkedIn often truncates long descriptions behind a "Show more" button.
    We need to click it to get the full content.
    """
    try:
        # Look for "Show more" button in the description section
        show_more_button = page.locator(
            ".description__text button:has-text('Show more')"
        )
        
        if show_more_button.is_visible():
            show_more_button.click()
            # Wait for the animation to complete
            page.wait_for_timeout(500)
    except Exception:
        # Button might not exist or already expanded - that's fine
        pass
