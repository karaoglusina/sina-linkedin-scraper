"""
Output generation for scraped job data.

This module handles:
- Saving jobs as JSON files
- Creating Markdown files with YAML frontmatter
- File naming and path handling

KEY CONCEPT: YAML Frontmatter
Markdown files can have metadata at the top in YAML format.
This is commonly used by static site generators and note-taking apps.

Example:
    ---
    title: "Job Title"
    company: "Company Name"
    ---
    
    # Content starts here...
"""

import json
import re
from pathlib import Path
from typing import Optional

from markdownify import markdownify as md

from .models import JobData


def save_as_json(job: JobData, output_dir: Path) -> Path:
    """
    Save job data as a JSON file.
    
    Creates/updates a single jobs.json file with the job data.
    If running multiple times, consider appending to an array instead.
    
    Args:
        job: JobData object to save
        output_dir: Directory to save the file in
        
    Returns:
        Path to the created file
    """
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert to dictionary with camelCase keys
    job_dict = job.to_dict()
    
    # Save to file
    output_path = output_dir / "jobs.json"
    
    # If file exists, try to append to existing array
    if output_path.exists():
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            
            # Handle both single object and array formats
            if isinstance(existing, list):
                # Check if job already exists (by ID)
                existing = [j for j in existing if j.get("id") != job_dict["id"]]
                existing.append(job_dict)
            else:
                # Convert single object to array
                if existing.get("id") != job_dict["id"]:
                    existing = [existing, job_dict]
                else:
                    existing = [job_dict]
            
            job_dict = existing
        except (json.JSONDecodeError, KeyError):
            # If parsing fails, just use the new job
            job_dict = [job_dict]
    else:
        # New file, start with array
        job_dict = [job_dict]
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(job_dict, f, indent=2, ensure_ascii=False)
    
    return output_path


def save_as_markdown(job: JobData, output_dir: Path) -> Path:
    """
    Save job data as a Markdown file with YAML frontmatter.
    
    The filename is: "<Job Title> <Company Name>.md"
    The description (converted from HTML) goes in the body, all other fields in frontmatter.
    
    Args:
        job: JobData object to save
        output_dir: Directory to save the file in
        
    Returns:
        Path to the created file
    """
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate safe filename
    filename = _sanitize_filename(f"{job.title} - {job.company_name}.md")
    output_path = output_dir / filename
    
    # Build YAML frontmatter
    frontmatter = _build_frontmatter(job)
    
    # Convert HTML description to Markdown for better formatting
    description_md = _html_to_markdown(job.description_html)
    
    # Combine frontmatter and description
    content = f"---\n{frontmatter}---\n\n{description_md}"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return output_path


def _html_to_markdown(html: str) -> str:
    """
    Convert HTML to clean Markdown.
    
    Uses markdownify library to convert:
    - <strong>/<b> → **bold**
    - <em>/<i> → *italic*
    - <ul><li> → bullet points
    - <br> → newlines
    - <a href="..."> → [text](url)
    """
    if not html:
        return ""
    
    # Convert HTML to Markdown
    markdown = md(
        html,
        heading_style="ATX",        # Use # for headers
        bullets="-",                 # Use - for bullet points
        strip=["button", "script", "style", "icon"],  # Remove unwanted elements
    )
    
    # Clean up excessive whitespace
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)  # Max 2 newlines
    markdown = re.sub(r' +', ' ', markdown)          # Single spaces
    
    # Remove "Show more" / "Show less" text
    markdown = re.sub(r'\s*Show more\s*', '', markdown)
    markdown = re.sub(r'\s*Show less\s*', '', markdown)
    
    # Convert middle dot bullet points (·) to proper markdown bullets
    markdown = re.sub(r'^·\s*', '- ', markdown, flags=re.MULTILINE)
    markdown = re.sub(r'\n·\s*', '\n- ', markdown)
    
    markdown = markdown.strip()
    
    return markdown


def _build_frontmatter(job: JobData) -> str:
    """
    Build YAML frontmatter string from job data.
    
    All fields except description go here.
    Values are quoted to handle special characters.
    """
    fields = [
        ("id", job.id),
        ("publishedAt", job.published_at),
        ("title", job.title),
        ("jobUrl", job.job_url),
        ("companyName", job.company_name),
        ("companyUrl", job.company_url),
        ("companyLogoUrl", job.company_logo_url),
        ("location", job.location),
        ("postedTime", job.posted_time),
        ("applicationsCount", job.applications_count),
        ("contractType", job.contract_type),
        ("experienceLevel", job.experience_level),
        ("workType", job.work_type),
        ("sector", job.sector),
        ("applyType", job.apply_type),
        ("applyUrl", job.apply_url),
        ("companyId", job.company_id),
        ("posterProfileUrl", job.poster_profile_url),
        ("posterFullName", job.poster_full_name),
    ]
    
    lines = []
    for key, value in fields:
        if value:  # Only include non-empty values
            # Escape quotes in the value
            escaped = str(value).replace('"', '\\"')
            lines.append(f'{key}: "{escaped}"')
    
    return "\n".join(lines) + "\n"


def _sanitize_filename(filename: str) -> str:
    """
    Remove or replace characters that are invalid in filenames.
    
    Different operating systems have different restrictions:
    - Windows: < > : " / \\ | ? *
    - macOS/Linux: / and null character
    
    We remove all of them for cross-platform compatibility.
    """
    # Remove invalid characters
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, "", filename)
    
    # Replace multiple spaces with single space
    sanitized = re.sub(r"\s+", " ", sanitized)
    
    # Trim whitespace
    sanitized = sanitized.strip()
    
    # Limit length (most filesystems support 255 characters)
    if len(sanitized) > 200:
        # Keep extension
        name, ext = sanitized.rsplit(".", 1) if "." in sanitized else (sanitized, "")
        sanitized = name[:200] + ("." + ext if ext else "")
    
    return sanitized or "unnamed_job.md"
