"""
Data structures for the LinkedIn job scraper.

Using dataclasses for clean, type-safe data containers.
Dataclasses automatically generate __init__, __repr__, and other methods.
"""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class JobData:
    """
    Represents a scraped LinkedIn job posting.
    
    All fields match the expected JSON output format.
    Optional fields may not be present on all job postings.
    """
    id: str
    published_at: str
    title: str
    job_url: str
    company_name: str
    company_url: str
    location: str
    posted_time: str
    applications_count: str
    description: str
    contract_type: str
    experience_level: str
    work_type: str
    sector: str
    apply_type: str
    apply_url: str
    company_id: str
    poster_profile_url: Optional[str]
    poster_full_name: Optional[str]
    description_html: str

    def to_dict(self) -> dict:
        """
        Convert to dictionary with camelCase keys for JSON output.
        
        Python convention is snake_case, but the output format uses camelCase.
        This method handles the conversion.
        """
        return {
            "id": self.id,
            "publishedAt": self.published_at,
            "title": self.title,
            "jobUrl": self.job_url,
            "companyName": self.company_name,
            "companyUrl": self.company_url,
            "location": self.location,
            "postedTime": self.posted_time,
            "applicationsCount": self.applications_count,
            "description": self.description,
            "contractType": self.contract_type,
            "experienceLevel": self.experience_level,
            "workType": self.work_type,
            "sector": self.sector,
            "applyType": self.apply_type,
            "applyUrl": self.apply_url,
            "companyId": self.company_id,
            "posterProfileUrl": self.poster_profile_url,
            "posterFullName": self.poster_full_name,
            "descriptionHtml": self.description_html,
        }
