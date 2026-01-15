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

from .types import JobData


def extract_job_data(page: Page, url: str) -> JobData:
    """
    Extract all job data from a LinkedIn job page.
    
    This is the main entry point for parsing.
    It coordinates extraction of all fields and returns a JobData object.
    
    Args:
        page: Playwright page object with loaded job posting
        url: Original URL (used for ID extraction and as fallback)
        
    Returns:
        JobData object with all extracted fields
    """
    # Extract basic info from the top card
    title = _extract_text(page, ".top-card-layout__title")
    company_name = _extract_text(page, ".topcard__org-name-link")
    location = _extract_text(page, ".topcard__flavor--bullet")
    
    # Extract URLs
    company_url = _extract_href(page, ".topcard__org-name-link")
    job_url = url  # Use the provided URL
    
    # Extract timing info
    posted_time = _extract_text(page, ".posted-time-ago__text")
    applications_count = _extract_text(page, ".num-applicants__caption")
    
    # Extract description (both text and HTML)
    description = _extract_text(page, ".description__text")
    description_html = _extract_html(page, ".description__text")
    
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
    
    return JobData(
        id=job_id,
        published_at=published_at,
        title=title,
        job_url=job_url,
        company_name=company_name,
        company_url=company_url,
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
        poster_profile_url=poster_info.get("url"),
        poster_full_name=poster_info.get("name"),
        description_html=description_html,
    )


def _extract_text(page: Page, selector: str) -> str:
    """
    Extract and clean text content from an element.
    
    KEY CONCEPT: Safe extraction
    - Always handle the case where the element doesn't exist
    - Clean whitespace from extracted text
    - Return empty string instead of None for consistency
    """
    try:
        element = page.locator(selector).first
        text = element.text_content() or ""
        # Clean up common noise
        text = text.strip()
        # Remove "Show more" / "Show less" buttons text
        text = re.sub(r'\s*Show more\s*', '', text)
        text = re.sub(r'\s*Show less\s*', '', text)
        return text.strip()
    except Exception:
        return ""


def _extract_href(page: Page, selector: str) -> str:
    """
    Extract href attribute and convert to absolute URL.
    
    LinkedIn often uses relative URLs. We convert them to absolute URLs
    for consistency and usability.
    """
    try:
        element = page.locator(selector).first
        href = element.get_attribute("href") or ""
        if href and not href.startswith("http"):
            return urljoin("https://www.linkedin.com", href)
        return href
    except Exception:
        return ""


def _extract_html(page: Page, selector: str) -> str:
    """
    Extract inner HTML of an element.
    
    We keep the HTML for rich formatting in the output.
    """
    try:
        element = page.locator(selector).first
        return element.inner_html() or ""
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
    
    Some job postings show the recruiter/poster's profile.
    """
    info = {}
    
    try:
        # Poster section might have different class names
        poster_link = page.locator(
            ".message-the-recruiter a, .hirer-card__hirer-information a"
        ).first
        
        if poster_link.is_visible():
            info["url"] = poster_link.get_attribute("href") or ""
            info["name"] = poster_link.text_content().strip()
            
            if info["url"] and not info["url"].startswith("http"):
                info["url"] = urljoin("https://www.linkedin.com", info["url"])
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
