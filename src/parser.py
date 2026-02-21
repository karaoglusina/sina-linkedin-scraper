"""
Data extraction and cleaning from LinkedIn job pages.

This module handles:
- Querying the DOM for specific elements
- Extracting text and attributes
- Cleaning and normalizing the data
- Converting relative dates to ISO format

KEY CONCEPT: Selectors
CSS selectors identify elements in the HTML document.
We use class-based selectors (e.g., ".top-card-layout__title") because:
- They're more stable than position-based selectors
- LinkedIn uses BEM naming convention (Block__Element--Modifier)
- They're descriptive and self-documenting
"""

import re
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse, parse_qs
from playwright.sync_api import Page
from typing import Optional

from .models import JobData
from .output import _html_to_markdown


def extract_job_data(page: Page, url: str) -> JobData:
    """
    Extract all job data from a LinkedIn job page.

    Supports both the public (logged-out) view and the authenticated
    (logged-in) view, which use entirely different CSS selectors.

    Args:
        page: Playwright page object with loaded job posting
        url: Original URL (used for ID extraction and as fallback)

    Returns:
        JobData object with all extracted fields
    """
    # --- Basic info ---
    # CSS class names in the logged-in SPA view are hashed and unstable.
    # We try named selectors first (logged-out), then fall back to JS evaluation
    # which uses structural/semantic queries that survive class-name changes.
    # ------------------------------------------------------------------
    # Title: In the logged-in SPA the title is a <p> inside [role="toolbar"],
    # NOT a heading element.  The toolbar first <p> without a bullet separator
    # (•) is the job title.
    # ------------------------------------------------------------------
    title = _extract_text_first(page,
        ".top-card-layout__title",   # logged-out
        ".topcard__title",
    ) or _extract_via_js(page, """
        (() => {
            // Most reliable: parse from page title — LinkedIn always sets it to
            // "(N) Job Title | Company | LinkedIn" or "Job Title | Company | LinkedIn"
            const pageTitle = (document.title || '').replace(/^\\(\\d+\\)\\s*/, '');
            const parts = pageTitle.split('|').map(s => s.trim());
            if (parts.length >= 2 && parts[0] && parts[0].length < 150) {
                return parts[0];
            }
            return '';
        })()
    """)

    # ------------------------------------------------------------------
    # Company name: first /company/ link inside main (not nav/header)
    # ------------------------------------------------------------------
    company_name = _extract_text_first(page,
        ".topcard__org-name-link",
    ) or _extract_via_js(page, """
        (() => {
            const main = document.querySelector('main') || document.body;
            const links = Array.from(main.querySelectorAll('a[href*="/company/"]'));
            for (const a of links) {
                const t = (a.innerText || '').trim();
                if (t && t.length < 120 && !t.includes('•')) return t;
            }
            return '';
        })()
    """)

    # ------------------------------------------------------------------
    # Location: In the SPA, location/time/applicants live in a single <p>
    # separated by "·": "Location · 2 months ago · 65 applicants"
    # inside [data-view-name="job-detail-page"].
    # ------------------------------------------------------------------
    _info_line_js = """
        (() => {
            const jp = document.querySelector('[data-view-name="job-detail-page"]')
                    || document.querySelector('main') || document.body;
            const ps = Array.from(jp.querySelectorAll('p'));
            for (const p of ps) {
                const t = (p.innerText || '').trim();
                if (t.includes('·') && /\\d+\\s+(day|week|month|hour|minute|year)s?\\s+ago/i.test(t))
                    return t;
            }
            return '';
        })()
    """
    _info_line = _extract_via_js(page, _info_line_js)
    _info_parts = [p.strip() for p in _info_line.split('·')] if _info_line else []

    location = _extract_text_first(page,
        ".topcard__flavor--bullet",
    ) or (_info_parts[0] if len(_info_parts) >= 1 else "")

    # --- URLs ---
    company_url = _extract_href_first(page,
        ".topcard__org-name-link",
    ) or _extract_via_js(page, """
        (() => {
            const link = document.querySelector('a[href*="/company/"]');
            return link ? link.href : '';
        })()
    """)

    company_logo_url = _extract_company_logo(page)
    # Normalise the job URL — strip query params and fragment
    _parsed = urlparse(url)
    job_url = f"{_parsed.scheme}://{_parsed.netloc}{_parsed.path}"

    # --- Timing / applicants ---
    # Reuse _info_parts parsed from the "Location · time · applicants" line
    posted_time = _extract_text_first(page,
        ".posted-time-ago__text",
    ) or (_info_parts[1] if len(_info_parts) >= 2 else "")

    applications_count = _extract_text_first(page,
        ".num-applicants__caption",
    ) or (_info_parts[2] if len(_info_parts) >= 3 else "")

    # --- Description ---
    # Logged-out view uses .description__text.
    # Logged-in SPA uses data-testid="expandable-text-box" inside
    # the "About the job" section — this is a stable LinkedIn test ID.
    description_html = _extract_html_first(page,
        ".description__text",
        "#job-details",
        '[data-testid="expandable-text-box"]',
    ) or _extract_via_js(page, """
        (() => {
            const el = document.querySelector('[data-testid="expandable-text-box"]')
                     || document.querySelector('#job-details')
                     || document.querySelector('.jobs-description');
            return el ? el.innerHTML : '';
        })()
    """)
    description = _html_to_markdown(description_html) if description_html else ""
    
    # Extract job criteria (seniority, employment type, etc.)
    criteria = _extract_job_criteria(page)
    
    # Extract poster info (who posted the job)
    poster_info = _extract_poster_info(page)
    
    # Extract IDs and apply info
    job_id = _extract_job_id(url)
    company_id = _extract_company_id(company_url)
    apply_type, apply_url = _extract_apply_info(page, url)
    
    # Calculate published date from relative time
    published_at = _parse_relative_time(posted_time)

    # --- Application status (logged-in SPA only) ---
    # If the user has applied, there's an "Application submitted" text followed
    # by a sibling <p> with the relative time (e.g. "1 month ago", "now").
    applied_time = _extract_via_js(page, """
        (() => {
            const ps = Array.from(document.querySelectorAll('p'));
            const submitted = ps.find(p => /application submitted|applied on/i.test(p.innerText));
            if (!submitted) return '';
            const next = submitted.nextElementSibling
                      || submitted.parentElement?.querySelector('p:nth-child(2)');
            if (next && next.tagName === 'P') {
                const t = next.innerText.trim();
                if (t && t.length < 40) return t;
            }
            return '';
        })()
    """)
    applied_at = _parse_relative_time(applied_time) if applied_time else ""

    return JobData(
        id=job_id,
        published_at=published_at,
        title=title,
        job_url=job_url,
        company_name=company_name,
        company_url=company_url,
        company_logo_url=company_logo_url,
        location=location,
        posted_time=posted_time,
        applications_count=applications_count,
        description=description,
        contract_type=criteria.get("Employment type", ""),
        experience_level=criteria.get("Seniority level", ""),
        work_type=criteria.get("Job function", ""),
        sector=criteria.get("Industries", ""),
        apply_type=apply_type,
        apply_url=apply_url,
        company_id=company_id,
        applied_time=applied_time or None,
        applied_at=applied_at or None,
        poster_profile_url=poster_info.get("url"),
        poster_full_name=poster_info.get("name"),
        description_html=description_html,
    )


def _extract_via_js(page: Page, js_expr: str) -> str:
    """
    Evaluate a JS expression and return the result as a cleaned string.
    Used as a fallback when CSS class names are hashed/unstable (logged-in SPA).
    """
    try:
        result = page.evaluate(js_expr)
        text = (result or "").strip()
        text = re.sub(r'\s*Show more\s*', '', text)
        text = re.sub(r'\s*Show less\s*', '', text)
        return text.strip()
    except Exception:
        return ""


def _extract_text(page: Page, selector: str) -> str:
    """Extract and clean text content from a single selector."""
    try:
        locator = page.locator(selector)
        if locator.count() == 0:   # instant check — no waiting
            return ""
        text = locator.first.text_content(timeout=2000) or ""
        text = text.strip()
        text = re.sub(r'\s*Show more\s*', '', text)
        text = re.sub(r'\s*Show less\s*', '', text)
        return text.strip()
    except Exception:
        return ""


def _extract_text_first(page: Page, *selectors: str) -> str:
    """
    Try each selector in order; return the first non-empty text found.
    Handles both the logged-out (public) and logged-in LinkedIn page layouts.
    """
    for selector in selectors:
        result = _extract_text(page, selector)
        if result:
            return result
    return ""


def _extract_href(page: Page, selector: str) -> str:
    """Extract href attribute and convert to absolute URL."""
    try:
        locator = page.locator(selector)
        if locator.count() == 0:
            return ""
        href = locator.first.get_attribute("href", timeout=2000) or ""
        if href and not href.startswith("http"):
            return urljoin("https://www.linkedin.com", href)
        return href
    except Exception:
        return ""


def _extract_href_first(page: Page, *selectors: str) -> str:
    """Try each selector in order; return the first non-empty href found."""
    for selector in selectors:
        result = _extract_href(page, selector)
        if result:
            return result
    return ""


def _extract_html(page: Page, selector: str) -> str:
    """Extract inner HTML of an element."""
    try:
        locator = page.locator(selector)
        if locator.count() == 0:
            return ""
        return locator.first.inner_html(timeout=2000) or ""
    except Exception:
        return ""


def _extract_html_first(page: Page, *selectors: str) -> str:
    """Try each selector in order; return the first non-empty inner HTML found."""
    for selector in selectors:
        result = _extract_html(page, selector)
        if result:
            return result
    return ""


def _extract_image_src(page: Page, selector: str) -> str:
    """
    Extract the src attribute from an img element.
    
    LinkedIn company logos are typically in img tags with various selectors.
    Handles lazy-loaded images that may not be "visible" but exist in DOM.
    """
    try:
        locator = page.locator(selector)
        # Check if any elements match (count is fast, doesn't wait)
        if locator.count() == 0:
            return ""
        
        element = locator.first
        src = element.get_attribute("src", timeout=500) or ""
        if not src:
            src = element.get_attribute("data-delayed-url", timeout=500) or ""
        return src
    except Exception:
        return ""


def _extract_job_criteria(page: Page) -> dict:
    """
    Extract job criteria as key-value pairs.
    
    LinkedIn displays job criteria in a list:
    - Seniority level: Associate
    - Employment type: Full-time
    - Job function: Analyst, Finance
    - Industries: Transportation, Logistics
    
    We parse this into a dictionary for easy access.
    """
    criteria = {}
    
    try:
        # Try multiple selector patterns for job criteria
        # Pattern 1: description__job-criteria-item (older structure)
        items = page.locator(".description__job-criteria-item").all()
        
        if not items:
            # Pattern 2: job-criteria section with list items
            items = page.locator(".job-criteria-item, [class*='job-criteria'] li").all()
        
        for item in items:
            try:
                header = item.locator("h3, .job-criteria-subheader").text_content()
                value = item.locator("span, .job-criteria-text").text_content()
                
                if header and value:
                    criteria[header.strip()] = value.strip()
            except:
                continue
                
        # If still empty, try to extract from the description section
        if not criteria:
            criteria_section = page.locator(".description__job-criteria-list").first
            if criteria_section.is_visible():
                # Parse the section differently
                pass
                
    except Exception:
        pass
    
    return criteria


def _extract_poster_info(page: Page) -> dict:
    """
    Extract information about who posted the job.

    Logged-out view: .message-the-recruiter / .hirer-card__hirer-information
    Logged-in SPA:   "Meet the hiring team" section with a[href*="/in/"] link
    """
    info = {}

    # Strategy 1: logged-out named selectors
    try:
        poster_link = page.locator(
            ".message-the-recruiter a, .hirer-card__hirer-information a"
        ).first

        if poster_link.count() > 0 and poster_link.is_visible(timeout=500):
            info["url"] = poster_link.get_attribute("href", timeout=500) or ""
            info["name"] = (poster_link.text_content(timeout=500) or "").strip()

            if info["url"] and not info["url"].startswith("http"):
                info["url"] = urljoin("https://www.linkedin.com", info["url"])
    except Exception:
        pass

    # Strategy 2: logged-in SPA — find the poster name in the
    # "Meet the hiring team" section.  The outer <a> wraps the whole card
    # (name + degree + bio + "Job poster"), so we must find the INNER
    # <a href="/in/..."> which contains only the name text.
    if not info.get("name"):
        try:
            result = page.evaluate("""
                (() => {
                    const main = document.querySelector('main') || document.body;
                    // Find all /in/ profile links; pick the deepest (innermost) one
                    // that has short, clean text — that's the name-only link.
                    const links = Array.from(main.querySelectorAll('a[href*="/in/"]'));
                    for (const a of links) {
                        // Skip if this <a> contains another <a> (it's a wrapper)
                        if (a.querySelector('a[href*="/in/"]')) continue;
                        // Get only direct text (childNodes), not nested elements
                        let name = '';
                        for (const node of a.childNodes) {
                            if (node.nodeType === 3) name += node.textContent;
                        }
                        name = name.trim();
                        if (!name) name = (a.innerText || '').split('\\n')[0].trim();
                        const href = a.href || '';
                        if (!name || name.length < 3 || name.length > 60) continue;
                        if (/notification|message|sign in|job poster/i.test(name)) continue;
                        // Must look like a person name (letters, spaces, hyphens, apostrophes)
                        if (!/^[\\p{L}\\s.'-]+$/u.test(name)) continue;
                        return { name, url: href };
                    }
                    return null;
                })()
            """)
            if result:
                info["name"] = result["name"]
                info["url"] = result["url"]
        except Exception:
            pass

    return info


def _extract_job_id(url: str) -> str:
    """
    Extract the job ID from a LinkedIn job URL.
    
    LinkedIn job URLs contain a numeric ID:
    https://linkedin.com/jobs/view/business-analyst-at-company-4281659372
                                                                ^^^^^^^^^
    """
    match = re.search(r"(\d{8,})", url)
    return match.group(1) if match else ""


def _extract_company_id(company_url: str) -> str:
    """
    Extract company ID from the company URL if available.
    
    This might be in the URL path or as a query parameter.
    """
    if not company_url:
        return ""
    
    # Try to find numeric ID in the URL
    match = re.search(r"/company/([^/?]+)", company_url)
    if match:
        # The ID might be the company slug, not numeric
        return match.group(1)
    
    return ""


def _extract_apply_info(page: Page, fallback_url: str) -> tuple:
    """
    Extract apply type and URL.
    
    LinkedIn has two apply types:
    - EASY_APPLY: Apply directly on LinkedIn
    - EXTERNAL: Redirects to company's website
    """
    apply_type = "EXTERNAL"  # Default
    apply_url = fallback_url
    
    try:
        # Check for Easy Apply button
        easy_apply = page.locator(".jobs-apply-button--top-card")
        
        if easy_apply.is_visible():
            button_text = easy_apply.text_content() or ""
            if "Easy Apply" in button_text:
                apply_type = "EASY_APPLY"
                apply_url = fallback_url  # Easy Apply uses same URL
    except Exception:
        pass
    
    return apply_type, apply_url

def _extract_company_logo(page: Page) -> str:
    """
    Extract the company logo URL from the job page.
    
    LinkedIn displays company logos in the top card area.
    Uses multiple strategies with JavaScript evaluation for reliable extraction.
    """
    try:
        # Strategy 1: Use JavaScript to comprehensively search the DOM
        logo_url = page.evaluate("""
            () => {
                // Look for images in the top card area with various attributes
                
                // 1. Find by alt text containing "logo"
                const logoByAlt = document.querySelector('.top-card-layout__entity-image img[alt*="logo"], img[alt*="logo"]');
                if (logoByAlt?.src && logoByAlt.src.startsWith('http')) {
                    return logoByAlt.src;
                }
                
                // 2. Find by LinkedIn's entity photo classes
                const selectors = [
                    'img.EntityPhoto-square-2',
                    'img.EntityPhoto-square-3',
                    'img.EntityPhoto-square-4',
                    'img.ivm-view-attr__img--centered',
                    '.top-card-layout__entity-image img',
                    '.topcard__org-name-link img',
                    'img.artdeco-entity-image'
                ];
                
                for (const selector of selectors) {
                    const img = document.querySelector(selector);
                    if (img?.src && img.src.startsWith('http')) {
                        return img.src;
                    }
                }
                
                // 3. Find any img with 'company-logo' or 'company' in src
                const allImgs = Array.from(document.querySelectorAll('img'));
                for (const img of allImgs) {
                    if (img.src && (
                        img.src.includes('company-logo') || 
                        img.src.includes('/company/') ||
                        (img.alt && img.alt.toLowerCase().includes('logo'))
                    )) {
                        return img.src;
                    }
                }
                
                // 4. Check data attributes for lazy-loaded images
                for (const img of allImgs) {
                    const dataSrc = img.getAttribute('data-delayed-url') || 
                                   img.getAttribute('data-src') ||
                                   img.getAttribute('data-ghost-url');
                    if (dataSrc && dataSrc.startsWith('http')) {
                        return dataSrc;
                    }
                }
                
                return '';
            }
        """)
        
        if logo_url:
            return logo_url
            
    except Exception as e:
        # Fallback to CSS selector approach if JavaScript fails
        pass
    
    # Strategy 2: Try direct CSS selectors with Playwright
    selectors = [
        ".top-card-layout__entity-image img",
        ".topcard__org-name-link img",
        "img.EntityPhoto-square-2",
        "img.EntityPhoto-square-3",
        "img.artdeco-entity-image",
        "img[alt*='logo']",
    ]
    
    for selector in selectors:
        try:
            locator = page.locator(selector)
            if locator.count() > 0:
                element = locator.first
                # Try src first
                src = element.get_attribute("src", timeout=1000)
                if src and src.startswith("http"):
                    return src
                # Try data attributes
                for attr in ["data-delayed-url", "data-src", "data-ghost-url"]:
                    src = element.get_attribute(attr, timeout=500)
                    if src and src.startswith("http"):
                        return src
        except Exception:
            continue
    
    return ""

def _parse_relative_time(text: str) -> str:
    """
    Convert relative time string to ISO date format.
    
    Examples:
        "2 weeks ago" -> "2025-01-01"
        "3 days ago" -> "2025-01-12"
        "1 month ago" -> "2024-12-15"
    
    KEY CONCEPT: Date calculation
    We work backwards from today's date using the relative time.
    This is an approximation since we don't know the exact posting time.
    """
    if not text:
        return datetime.now().strftime("%Y-%m-%d")
    
    text = text.lower().strip()
    today = datetime.now()
    
    # Extract the number from the text
    numbers = re.findall(r"\d+", text)
    amount = int(numbers[0]) if numbers else 1
    
    # Calculate the date based on the time unit
    if "hour" in text or "minute" in text:
        result = today
    elif "day" in text:
        result = today - timedelta(days=amount)
    elif "week" in text:
        result = today - timedelta(weeks=amount)
    elif "month" in text:
        result = today - timedelta(days=amount * 30)
    elif "year" in text:
        result = today - timedelta(days=amount * 365)
    else:
        result = today
    
    return result.strftime("%Y-%m-%d")
