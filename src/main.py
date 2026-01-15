#!/usr/bin/env python3
"""
LinkedIn Job Scraper - CLI Entry Point

Usage:
    # Single job
    python -m src.main "https://linkedin.com/jobs/view/..."
    
    # Batch from file (one URL per line)
    python -m src.main --batch urls.txt -m --md-dir ./jobs

Options:
    -m, --markdown      Also create a Markdown file
    -o, --output        JSON output directory (default: ./output)
    --md-dir            Markdown output directory (default: same as --output)
    --batch             File containing URLs (one per line)
    --no-headless       Show browser window (for debugging)
"""

import argparse
import sys
import time
from pathlib import Path

from .scraper import create_browser, navigate_to_job
from .parser import extract_job_data
from .output import save_as_json, save_as_markdown


def main():
    """Main entry point for the CLI."""
    args = parse_args()
    
    # Determine mode: batch or single
    if args.batch:
        run_batch(args)
    else:
        run_single(args)


def run_single(args):
    """Scrape a single job URL."""
    if not args.url:
        print("Error: Please provide a URL or use --batch with a file")
        sys.exit(1)
    
    if not is_valid_linkedin_url(args.url):
        print(f"Error: Invalid LinkedIn job URL: {args.url}")
        print("Expected format: https://linkedin.com/jobs/view/...")
        sys.exit(1)
    
    print(f"🔍 Scraping job: {args.url}")
    
    try:
        with create_browser(headless=not args.no_headless) as browser:
            print("🌐 Launching browser...")
            job_data = scrape_single_job(browser, args.url)
            save_job(job_data, args)
            print_job_summary(job_data)
    except Exception as e:
        print(f"❌ Error scraping job: {e}")
        sys.exit(1)


def run_batch(args):
    """Scrape multiple jobs from a file of URLs."""
    batch_file = Path(args.batch)
    
    if not batch_file.exists():
        print(f"Error: Batch file not found: {batch_file}")
        sys.exit(1)
    
    # Read URLs from file
    urls = read_urls_from_file(batch_file)
    
    if not urls:
        print("Error: No valid URLs found in batch file")
        sys.exit(1)
    
    print(f"📋 Found {len(urls)} jobs to scrape\n")
    
    # Track results
    successful = 0
    failed = 0
    failed_urls = []
    
    # Reuse browser for all jobs (much faster!)
    with create_browser(headless=not args.no_headless) as browser:
        print("🌐 Browser launched (reusing for all jobs)\n")
        
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] Scraping: {url[:60]}...")
            
            try:
                job_data = scrape_single_job(browser, url)
                save_job(job_data, args)
                print(f"  ✅ {job_data.title} at {job_data.company_name}")
                successful += 1
                
                # Small delay between jobs to be respectful
                if i < len(urls):
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"  ❌ Failed: {e}")
                failed += 1
                failed_urls.append(url)
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"📊 Batch complete!")
    print(f"   ✅ Successful: {successful}")
    print(f"   ❌ Failed: {failed}")
    
    if failed_urls:
        print(f"\n   Failed URLs:")
        for url in failed_urls:
            print(f"   - {url}")


def read_urls_from_file(file_path: Path) -> list:
    """
    Read URLs from a file, one per line.
    
    Skips empty lines and lines starting with #
    """
    urls = []
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            
            # Validate URL
            if is_valid_linkedin_url(line):
                urls.append(line)
            else:
                print(f"⚠️  Skipping invalid URL: {line[:50]}...")
    
    return urls


def scrape_single_job(browser, url: str):
    """Scrape a single job with an existing browser."""
    page = navigate_to_job(browser, url)
    job_data = extract_job_data(page, url)
    page.close()
    return job_data


def save_job(job_data, args):
    """Save job to JSON and optionally Markdown."""
    json_dir = Path(args.output)
    md_dir = Path(args.md_dir) if args.md_dir else json_dir
    
    # Always save JSON
    save_as_json(job_data, json_dir)
    
    # Optionally save Markdown
    if args.markdown:
        save_as_markdown(job_data, md_dir)


def print_job_summary(job_data):
    """Print a summary of a scraped job."""
    print(f"\n📋 Job: {job_data.title} at {job_data.company_name}")
    print(f"📍 Location: {job_data.location}")
    print(f"📅 Posted: {job_data.posted_time}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Scrape LinkedIn job postings and save as JSON/Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Scrape a single job
    python -m src.main "https://linkedin.com/jobs/view/..."
    
    # Scrape with Markdown output
    python -m src.main "https://linkedin.com/jobs/view/..." -m
    
    # Batch scrape from file
    python -m src.main --batch urls.txt -m
    
    # Batch with custom Markdown directory
    python -m src.main --batch urls.txt -m --md-dir ~/Documents/Jobs
        """
    )
    
    parser.add_argument(
        "url",
        nargs="?",  # Optional when using --batch
        help="LinkedIn job posting URL"
    )
    
    parser.add_argument(
        "--batch",
        metavar="FILE",
        help="File containing URLs to scrape (one per line)"
    )
    
    parser.add_argument(
        "-m", "--markdown",
        action="store_true",
        help="Also create Markdown files with YAML frontmatter"
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
    """Validate that the URL is a LinkedIn job posting."""
    url_lower = url.lower()
    return "linkedin.com" in url_lower and "/jobs/view/" in url_lower


if __name__ == "__main__":
    main()
