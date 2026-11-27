"""
Data Models for Job Posting Automation
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class Location:
    """Model for location information"""
    location_id: str
    location_name: str
    is_custom_group: bool = False


@dataclass
class Education:
    """Model for education requirements"""
    ug_gid: Optional[Dict[str, Any]] = None
    pg_gid: Optional[Dict[str, Any]] = None
    ppg_gid: Optional[Dict[str, Any]] = None


@dataclass
class SalaryDetail:
    """Model for salary information"""
    minimum_salary: float
    maximum_salary: float
    currency: str = "INR"


@dataclass
class KeySkill:
    """Model for key skills"""
    skill_name: str
    is_preferred: bool = False

    def __str__(self):
        return f"{self.skill_name}{'*' if self.is_preferred else ''}"


@dataclass
class ResponseManagerSettings:
    """Model for response manager configuration"""
    response_manager_type: str  # 'rms', 'companyUrl', 'ATS'
    company_url: Optional[str] = None
    emails: Optional[List[str]] = None
    frequency: str = "On every new apply"
    subject_settings: Optional[Dict[str, Any]] = None
    relevance_rating: Optional[str] = None  # 'low' | 'medium' | 'high' - ORE.cs:615


@dataclass
class Job:
    """Main Job Model - represents a job posting"""
    job_id: Optional[str] = None
    company_id: str = ""
    company_name: str = ""
    position: str = ""
    description: str = ""
    job_type: str = "h"  # 's', 'h', 'c'

    # Experience
    min_experience: int = 0
    max_experience: int = 0

    # Salary
    salary_detail: Optional[SalaryDetail] = None

    # Location
    national_locations: List[Location] = field(default_factory=list)
    international_locations: List[Location] = field(default_factory=list)
    other_national_locations: Optional[List[str]] = None
    other_international_locations: Optional[List[str]] = None
    base_location: Optional[Dict[str, Any]] = None
    localities_gid: Optional[Dict[str, Any]] = None

    # Education
    education: Optional[Education] = None

    # Skills
    key_skills: Dict[str, Any] = field(default_factory=dict)
    mandatory_keywords: Optional[List[str]] = None

    # Categories
    industry_gid: str = ""
    functional_area_gid: str = ""
    job_role_gid: str = ""
    role_category_gid: str = ""
    candidate_industry: Optional[str] = None

    # Additional details
    roles_and_responsibilities: Optional[str] = None
    desired_candidate_profile: Optional[str] = None
    perks_and_benefits: Optional[str] = None
    company_profile: Optional[str] = None  # Comp_Profile from database - for companyDetail.details

    # Response Manager
    response_manager_settings: Optional[ResponseManagerSettings] = None
    responses: Optional[str] = None  # [Responses] - drives ResponseMode (Naukri.cs:1081-1096)
    response_mode: Optional[str] = None  # 'rms' | 'companyUrl' | 'ATS' - derived from responses
    response_url: Optional[str] = None  # [URL] - custom apply URL (RibbonController.cs:1328)
    auto_forward_email: Optional[str] = None  # Comma-joined emails (Naukri.cs:1157)
    email_response: Optional[str] = None  # 'Y'/'N' - drives frequency (ORE.cs:612)
    process: Optional[str] = None  # [Process] - 'premium' forces Daily summary (ORE.cs:605)
    paf_str: Optional[str] = None  # [PAF] - drives relevanceRating (ORE.cs:615)

    # Status
    status: str = "draft"  # draft, posted, live
    job_sent_id: Optional[str] = None  # [Sr No] - row identity before a Job Id exists
    requirement_id: Optional[str] = None
    requirement_name: Optional[str] = None
    reference_code: Optional[str] = None
    vacancy: int = 1

    # Additional flags
    is_wfh: bool = False
    wfh: Optional[str] = None  # WFH type from database ("2" for work from home)
    show_recruiter_detail: bool = True
    share_job_legacy_flag: bool = False

    # Assignment
    assigned_sub_users: List[int] = field(default_factory=list)

    # Metadata
    created_date: Optional[datetime] = None
    updated_date: Optional[datetime] = None
    posting_type: str = "h"

    def validate(self) -> tuple[bool, List[str]]:
        """Validate job data - returns (is_valid, error_list)"""
        errors = []

        if not self.position or len(self.position) < 3:
            errors.append("Position/Title cannot be blank")

        if len(self.position) > 70:
            errors.append("Job Title cannot be greater than 70 characters")

        if not self.description:
            errors.append("Job Description cannot be blank")

        if not self.national_locations and not self.international_locations:
            errors.append("At least one location is required")

        if (len(self.national_locations) + len(self.international_locations)) > 3:
            errors.append("Only 3 primary locations are allowed")

        if not self.key_skills:
            errors.append("Key Skills cannot be blank")

        if len(self.key_skills) < 3:
            errors.append("Minimum 3 key skills are required")

        if self.mandatory_keywords and len(self.mandatory_keywords) > 5:
            errors.append("Mandatory Keywords cannot be more than 5")

        if not self.education or (not self.education.ug_gid and not self.education.pg_gid):
            errors.append("Undergraduate education qualification is required")

        if self.min_experience > 30:
            errors.append("Minimum experience cannot be greater than 30 years")

        if not self.functional_area_gid:
            errors.append("Functional Area cannot be blank")

        if not self.industry_gid:
            errors.append("Industry cannot be blank")

        if not self.job_role_gid:
            errors.append("Job Role cannot be blank")

        if self.min_experience > self.max_experience:
            errors.append("Minimum experience cannot be greater than maximum experience")

        return len(errors) == 0, errors


@dataclass
class JobPostingRequest:
    """Request object for job posting with raw data from database"""
    row_data: Dict[str, Any]
    job_id: Optional[str] = None
    company_id: str = ""
    job_type: str = "h"
    source: str = "offline"

    def extract_field(self, field_name: str, default: Any = None) -> Any:
        """
        Safely extract a field from the row data, treating SQL NULLs as absent.

        pandas renders a NULL as None for a mixed text column but as float NaN
        for a column that is entirely NULL - and NaN is truthy, so a caller
        writing `extract_field(...) or fallback` would keep the NaN instead of
        taking its fallback. Blank and whitespace-only strings count as absent
        for the same reason.
        """
        if field_name not in self.row_data:
            return default

        value = self.row_data[field_name]

        if value is None:
            return default
        if isinstance(value, float) and value != value:  # NaN is never equal to itself
            return default
        if isinstance(value, str) and not value.strip():
            return default

        return value


@dataclass
class JobPostingResult:
    """Result of a job posting operation"""
    success: bool
    new_job_id: Optional[str] = None
    message: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    posting_timestamp: Optional[datetime] = None
    posting_duration_ms: int = 0
    original_job_id: Optional[str] = None
    company_id: str = ""
    # Carried back for the [Sr No] write-back after a successful post
    job_sent_id: Optional[str] = None
    posted_title: str = ""
    posted_location: str = ""
    all_info: str = ""
    # Where a job actually stopped, so a failed row can be diagnosed from the
    # results CSV alone: posted but not live, or live but not written to the DB.
    made_live: bool = False
    db_updated: bool = False
    # What was written to [Job_Listing Status]: "Posted", "Pending", or "" when
    # nothing was written at all.
    db_status: str = ""


@dataclass
class BulkPostingResult:
    """Result of bulk job posting operation"""
    total_jobs: int = 0
    successful_jobs: int = 0
    failed_jobs: int = 0
    results: List[JobPostingResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_jobs == 0:
            return 0.0
        return (self.successful_jobs / self.total_jobs) * 100


@dataclass
class SubUser:
    """Model for sub-users in a company"""
    user_id: int
    name: str
    email: str
    is_super_user: bool = False
    is_active: bool = True


@dataclass
class CompanyDetails:
    """Model for company information"""
    company_id: str
    company_name: str
    user_id: str
    subscription_id: Optional[str] = None
    sub_users: List[SubUser] = field(default_factory=list)
    credits_left: Optional[int] = None
