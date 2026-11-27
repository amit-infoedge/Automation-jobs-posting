"""
Example Usage Scripts for Job Posting Automation
Demonstrates various ways to use the automation framework
"""

import logging
from models import Job, Location, Education, SalaryDetail, ResponseManagerSettings
from job_processor import JobProcessor, JobValidator, JobBuilder
from job_poster import JobPoster
from database import DatabaseManager
from api_client import NaukriAPIClient
from config import ACTION_SAVE, ACTION_UPDATE
import pandas as pd

# Setup logging for examples
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Example 1: Validate a Job
def example_validate_job():
    """Example: Validate a job object"""
    logger.info("=" * 60)
    logger.info("EXAMPLE 1: Validate Job")
    logger.info("=" * 60)

    # Create a job
    job = Job(
        company_id="27117",
        company_name="Test Company",
        position="Senior Software Engineer",
        description="Looking for experienced software engineer",
        job_type="h",
        min_experience=3,
        max_experience=8,
        salary_detail=SalaryDetail(800000, 1200000, "INR"),
        national_locations=[
            Location("1", "Bangalore"),
            Location("2", "Delhi")
        ],
        key_skills={'Python': {'label': 'Python', 'preferred': True}},
        industry_gid="1",
        functional_area_gid="2",
        job_role_gid="3"
    )

    # Validate
    is_valid, errors = job.validate()
    logger.info(f"Job valid: {is_valid}")
    if errors:
        logger.error(f"Validation errors: {errors}")
    else:
        logger.info("Job validation passed!")


# Example 2: Parse Job Data
def example_parse_job_data():
    """Example: Parse experience and salary strings"""
    logger.info("\n" + "=" * 60)
    logger.info("EXAMPLE 2: Parse Job Data")
    logger.info("=" * 60)

    processor = JobProcessor()

    # Parse experience
    min_exp, max_exp = processor.parse_experience("3-8 years")
    logger.info(f"Experience parsed: {min_exp}-{max_exp} years")

    # Parse salary
    min_sal, max_sal, currency = processor.parse_salary("8-12 LPA")
    logger.info(f"Salary parsed: {min_sal:,.0f} - {max_sal:,.0f} {currency}")

    # Parse keywords
    keywords = processor.parse_keywords("Python,Java*,SQL,Linux*")
    logger.info(f"Keywords parsed: {len(keywords)} skills")
    for ks in keywords:
        logger.info(f"  - {ks.skill_name} (preferred: {ks.is_preferred})")


# Example 3: Validate Keywords
def example_validate_keywords():
    """Example: Validate keywords"""
    logger.info("\n" + "=" * 60)
    logger.info("EXAMPLE 3: Validate Keywords")
    logger.info("=" * 60)

    validator = JobValidator()

    # Valid keywords
    is_valid, error = validator.validate_keywords(['Python', 'Java', 'SQL'])
    logger.info(f"Valid keywords: {is_valid}")

    # Invalid keywords (too few)
    is_valid, error = validator.validate_keywords(['Python'])
    logger.info(f"One keyword - Valid: {is_valid}, Error: {error}")

    # Invalid keywords (too many)
    is_valid, error = validator.validate_keywords(
        ['Python', 'Java', 'SQL', 'C++', 'Go', 'Rust', 'JS', 'PHP', 'C#', 'Swift', 'Kotlin']
    )
    logger.info(f"11 keywords - Valid: {is_valid}, Error: {error}")


# Example 4: Fetch Jobs from Database
def example_fetch_jobs():
    """Example: Fetch jobs from database"""
    logger.info("\n" + "=" * 60)
    logger.info("EXAMPLE 4: Fetch Jobs from Database")
    logger.info("=" * 60)

    try:
        db = DatabaseManager()

        # Fetch jobs for specific companies
        df = db.fetch_jobs_for_posting([27117, 16987])

        if not df.empty:
            logger.info(f"Fetched {len(df)} jobs")
            logger.info(f"Columns: {list(df.columns)}")
            logger.info(f"Sample data:\n{df.head()}")
        else:
            logger.info("No jobs found")

    except Exception as e:
        logger.error(f"Error: {str(e)}")


# Example 5: Build Job from Raw Data
def example_build_job():
    """Example: Build Job object from raw request"""
    logger.info("\n" + "=" * 60)
    logger.info("EXAMPLE 5: Build Job from Raw Data")
    logger.info("=" * 60)

    from models import JobPostingRequest

    processor = JobProcessor()
    builder = JobBuilder(processor)

    # Raw data from database
    raw_data = {
        'title': 'Python Developer',
        'description': 'Experienced Python developer needed',
        'Exp_Str': '2-5 years',
        'CTC_Str': '8-12 LPA',
        'Keywords': 'Python,Django,PostgreSQL',
        'Industry_Id': '1',
        'Farea': '2',
        'Role': '3'
    }

    # Create request
    request = JobPostingRequest(
        row_data=raw_data,
        job_id='202312312345',
        company_id='27117',
        job_type='h'
    )

    # Build job
    job, errors = builder.build_from_request(request)

    if errors:
        logger.error(f"Build errors: {errors}")
    else:
        logger.info(f"Job built successfully:")
        logger.info(f"  Position: {job.position}")
        logger.info(f"  Experience: {job.min_experience}-{job.max_experience} years")
        logger.info(f"  Skills: {list(job.key_skills.keys())}")


# Example 6: Apply Business Rules
def example_business_rules():
    """Example: Apply business rules to job"""
    logger.info("\n" + "=" * 60)
    logger.info("EXAMPLE 6: Apply Business Rules")
    logger.info("=" * 60)

    processor = JobProcessor()

    # Create a job
    job = Job(
        position="Software Engineer",
        description="Job description here",
        min_experience=5,
        max_experience=10,
        national_locations=[Location("1", "Bangalore")],
        key_skills={'Python': {'label': 'Python'}},
        industry_gid="1",
        functional_area_gid="2",
        job_role_gid="3"
    )

    # Apply rules
    is_valid, errors = processor.apply_business_rules(job)
    logger.info(f"Business rules valid: {is_valid}")
    if errors:
        logger.error(f"Rule violations: {errors}")
    else:
        logger.info("All business rules passed!")


# Example 7: Post Individual Job
def example_post_single_job():
    """Example: Post a single job"""
    logger.info("\n" + "=" * 60)
    logger.info("EXAMPLE 7: Post Single Job")
    logger.info("=" * 60)

    # Note: This requires valid authentication cookies and user ID
    cookies = {
        # Add your cookies here
        # 'inauk_at': 'your_token',
        # 'inauk_rt': 'your_refresh_token'
    }
    user_id = "your_user_id"

    if not cookies or not user_id:
        logger.warning("Skipping: Authentication credentials not provided")
        logger.info("Add valid cookies and user_id to run this example")
        return

    try:
        # Initialize poster
        poster = JobPoster('27117', user_id, cookies)

        if not poster.initialize():
            logger.error("Failed to initialize poster")
            return

        logger.info(f"Poster initialized for {poster.company_details.company_name}")

        # Create job
        job = Job(
            company_id="27117",
            company_name="Test Company",
            position="Test Software Engineer",
            description="This is a test job",
            job_type="h",
            min_experience=2,
            max_experience=5,
            salary_detail=SalaryDetail(500000, 800000),
            national_locations=[Location("1", "Bangalore")],
            key_skills={'Python': {'label': 'Python', 'preferred': True}},
            industry_gid="1",
            functional_area_gid="2",
            job_role_gid="3"
        )

        # Post job
        result = poster.post_job(job, ACTION_SAVE)
        logger.info(f"Job posting result: {result.success}")
        logger.info(f"Message: {result.message}")
        if result.new_job_id:
            logger.info(f"New Job ID: {result.new_job_id}")

        poster.cleanup()

    except Exception as e:
        logger.error(f"Error: {str(e)}")


# Example 8: Clean Data
def example_clean_data():
    """Example: Clean job data"""
    logger.info("\n" + "=" * 60)
    logger.info("EXAMPLE 8: Clean Data")
    logger.info("=" * 60)

    from utils import DataCleaner

    cleaner = DataCleaner()

    # Clean strings
    title = "  Software Engineer  "
    cleaned = cleaner.clean_string(title, strip=True, lowercase=False)
    logger.info(f"Original: '{title}' -> Cleaned: '{cleaned}'")

    # Handle encoding
    jd = "This has a non-breaking space"
    cleaned_jd = cleaner.handle_encoding(jd)
    logger.info(f"JD with special chars cleaned")

    # Clean numeric
    value = "not_a_number"
    cleaned_num = cleaner.clean_numeric(value, default=0.0)
    logger.info(f"Non-numeric '{value}' -> {cleaned_num}")


# Example 9: Validate Fields
def example_validate_fields():
    """Example: Validate required fields"""
    logger.info("\n" + "=" * 60)
    logger.info("EXAMPLE 9: Validate Required Fields")
    logger.info("=" * 60)

    from utils import ValidationUtils

    validator = ValidationUtils()

    # Validate email
    email = "test@example.com"
    is_valid = validator.is_valid_email(email)
    logger.info(f"Email '{email}' valid: {is_valid}")

    # Validate URL
    url = "https://www.example.com"
    is_valid = validator.is_valid_url(url)
    logger.info(f"URL '{url}' valid: {is_valid}")

    # Validate job ID
    job_id = "202312312345"
    is_valid = validator.is_valid_job_id(job_id)
    logger.info(f"Job ID '{job_id}' valid: {is_valid}")

    # Validate required fields
    data = {
        'title': 'Software Engineer',
        'description': '',  # Missing
        'location': 'Bangalore'
    }
    missing = validator.validate_required_fields(
        data,
        ['title', 'description', 'location', 'salary']  # salary also missing
    )
    logger.info(f"Missing fields: {missing}")


# Example 10: Time Utilities
def example_time_utilities():
    """Example: Time and date utilities"""
    logger.info("\n" + "=" * 60)
    logger.info("EXAMPLE 10: Time Utilities")
    logger.info("=" * 60)

    from utils import TimeUtils

    time_util = TimeUtils()

    # Current timestamp
    current = time_util.get_current_timestamp()
    logger.info(f"Current timestamp: {current}")

    # File timestamp
    file_ts = time_util.get_file_timestamp()
    logger.info(f"File timestamp: {file_ts}")

    # Check if date is past
    past_date = time_util.is_past_date("2020-01-01")
    logger.info(f"Is 2020-01-01 in past: {past_date}")

    # Days since
    days = time_util.days_since("2024-01-01")
    logger.info(f"Days since 2024-01-01: {days}")


# Run all examples
def run_all_examples():
    """Run all examples"""
    examples = [
        ("Validate Job", example_validate_job),
        ("Parse Job Data", example_parse_job_data),
        ("Validate Keywords", example_validate_keywords),
        ("Fetch Jobs", example_fetch_jobs),
        ("Build Job", example_build_job),
        ("Business Rules", example_business_rules),
        ("Post Single Job", example_post_single_job),
        ("Clean Data", example_clean_data),
        ("Validate Fields", example_validate_fields),
        ("Time Utilities", example_time_utilities),
    ]

    for name, func in examples:
        try:
            func()
        except Exception as e:
            logger.error(f"Error in {name}: {str(e)}")


if __name__ == "__main__":
    logger.info("Job Posting Automation - Examples")
    logger.info("=" * 60)
    run_all_examples()
    logger.info("\n" + "=" * 60)
    logger.info("Examples completed")
