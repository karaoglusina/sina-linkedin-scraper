#!/usr/bin/env python3
"""
LinkedIn Job Scraper - CLI Entry Point

Usage:
    python -m src.main "https://linkedin.com/jobs/view/..." [options]

Options:
    -m, --markdown      Also create a Markdown file
    -o, --output        JSON output directory (default: ./output)
    --md-dir            Markdown output directory (default: same as --output)
    --no-headless       Show browser window (for debugging)
"""

import argparse
import sys
from pathlib import Path

from .scraper import create_browser, navigate_to_job
from .parser import extract_job_data
from .output import save_as_json, save_as_markdown


def main():
    """Main entry point for the CLI."""
    # Parse command line arguments
    args = parse_args()
    
    # Validate URL
    if not is_valid_linkedin_url(args.url):
        print(f"Error: Invalid LinkedIn job URL: {args.url}")
        print("Expected format: https://linkedin.com/jobs/view/...")
        sys.exit(1)
    
    print(f"🔍 Scraping job: {args.url}")
    
    try:
        # Scrape the job
        job_data = scrape_job(args.url, headless=not args.no_headless)
        
        # Save outputs
        json_dir = Path(args.output)
        md_dir = Path(args.md_dir) if args.md_dir else json_dir
        
        # Always save JSON
        json_path = save_as_json(job_data, json_dir)
        print(f"✅ Saved JSON: {json_path}")
        
        # Optionally save Markdown
        if args.markdown:
            md_path = save_as_markdown(job_data, md_dir)
            print(f"✅ Saved Markdown: {md_path}")
        
        print(f"\n📋 Job: {job_data.title} at {job_data.company_name}")
        print(f"📍 Location: {job_data.location}")
        print(f"📅 Posted: {job_data.posted_time}")
        
    except Exception as e:
        print(f"❌ Error scraping job: {e}")
        sys.exit(1)


def parse_args():
    """
    Parse command line arguments.
    
    Using argparse (Python's built-in argument parser) for:
    - Automatic help message generation
    - Type validation
    - Default values
    """
    parser = argparse.ArgumentParser(
        description="Scrape LinkedIn job postings and save as JSON/Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Scrape a job (JSON only)
    python -m src.main "https://linkedin.com/jobs/view/..."
    
    # Scrape with Markdown output (same directory)
    python -m src.main "https://linkedin.com/jobs/view/..." -m
    
    # Custom JSON directory
    python -m src.main "https://linkedin.com/jobs/view/..." -o ./data
    
    # JSON and Markdown in different directories
    python -m src.main "https://linkedin.com/jobs/view/..." -m -o ./data --md-dir ./notes
    
    # Markdown to a specific folder (e.g., Obsidian vault)
    python -m src.main "https://linkedin.com/jobs/view/..." -m --md-dir ~/Documents/Obsidian/Jobs
        """
    )
    
    parser.add_argument(
        "url",
        help="LinkedIn job posting URL"
    )
    
    parser.add_argument(
        "-m", "--markdown",
        action="store_true",
        help="Also create a Markdown file with YAML frontmatter"
    )
    
    parser.add_argument(
        "-o", "--output",
        default="./output",
        help="JSON output directory (default: ./output)"
    )
    
    parser.add_argument(
        "--md-dir",
        default=None,
        help="Markdown output directory (default: same as --output)"
    )
    
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show browser window (useful for debugging)"
    )
    
    return parser.parse_args()


def is_valid_linkedin_url(url: str) -> bool:
    """
    Validate that the URL is a LinkedIn job posting.
    
    We check for:
    - linkedin.com domain
    - /jobs/view/ path
    """
    url_lower = url.lower()
    return (
        "linkedin.com" in url_lower and
        "/jobs/view/" in url_lower
    )


def scrape_job(url: str, headless: bool = True):
    """
    Scrape a single job posting.
    
    This orchestrates the scraping process:
    1. Launch browser
    2. Navigate to URL
    3. Extract data
    4. Close browser
    
    Args:
        url: LinkedIn job URL
        headless: Whether to hide the browser window
        
    Returns:
        JobData object with extracted information
    """
    with create_browser(headless=headless) as browser:
        print("🌐 Launching browser...")
        
        page = navigate_to_job(browser, url)
        print("📄 Page loaded, extracting data...")
        
        job_data = extract_job_data(page, url)
        
        # Close the page
        page.close()
        
        return job_data


if __name__ == "__main__":
    main()
