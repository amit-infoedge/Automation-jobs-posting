# Job Posting Automation Framework

A comprehensive Python framework for automating job postings to Naukri platform with robust business logic, validation, and error handling.

## Overview

This framework provides a complete solution for:
- **Fetching jobs** from SQL database (with specific company IDs and status filters)
- **Processing jobs** with business logic (title validation, keyword parsing, experience/salary parsing)
- **Predicting missing fields** based on job description
- **Posting jobs** to Naukri API with complete validation
- **Bulk operations** with concurrent job posting
- **Result tracking** and reporting

## Architecture

### Module Structure

```
python code/
├── config.py              # Configuration and constants
├── models.py              # Data models and classes
├── database.py            # Database connection and operations
├── job_processor.py       # Business logic and job processing
├── api_client.py          # Naukri API client
├── job_poster.py          # Job posting orchestrator
├── utils.py               # Utility functions
├── main.py                # Entry point and main workflow
└── README.md              # This file
```

## Core Components

### 1. **config.py** - Configuration
Centralized configuration for:
- Database connection details
- API endpoints and timeouts
- Target company IDs for automation
- Output directories
- Email notifications

**Key Variables:**
- `TARGET_COMPANY_IDS`: List of company IDs to process `[27117, 16987]`
- `API_TIMEOUT`: Request timeout (30 seconds)
- `API_RETRY_COUNT`: Number of retry attempts (3)

### 2. **models.py** - Data Models
Complete data models including:

- **Job**: Main job posting model with validation
  - Position, description, experience, salary
  - Locations (national & international)
  - Education requirements
  - Key skills and keywords
  - Response manager settings
  
- **JobPostingRequest**: Request wrapper for raw data
- **JobPostingResult**: Result of single job posting
- **BulkPostingResult**: Summary of bulk operation
- **SubUser**: Sub-user representation
- **CompanyDetails**: Company information

### 3. **database.py** - Database Layer

**DatabaseConnection Class:**
- Connects to SQL Server database
- Fetches jobs with status filtering
- Updates job statuses
- Logs posting attempts
- Checks for duplicate postings

**Key Methods:**
```python
fetch_jobs_for_posting(company_ids)  # Fetch jobs from database
update_job_status(job_id, status)    # Update job status
insert_job_posting_result(data)      # Save posting results
log_posting_attempt(log_data)        # Log attempts
```

### 4. **job_processor.py** - Business Logic

**JobValidator Class:**
- Validates job titles (max 70 chars, no invalid characters)
- Validates keywords (min 3, max 10)
- Validates locations (1-3 primary locations)
- Validates experience range
- Validates education requirements

**JobProcessor Class:**
- Parse experience strings: "2-5 years" → (2, 5)
- Parse salary strings: "10-20 LPA" → (1000000, 2000000)
- Parse keywords: "Java,Python*,SQL" → KeySkill objects with preferred flag
- Fill blank fields with defaults
- Apply business rules
- Clean JD by removing buzzwords
- Predict missing fields from JD text

**JobBuilder Class:**
- Builds complete Job object from raw request data
- Handles all field transformations
- Applies defaults
- Provides error reporting

### 5. **api_client.py** - API Integration

**NaukriAPIClient Class:**
- Handles all API communications
- Implements retry logic with exponential backoff
- Manages authentication cookies
- Provides methods for:
  - Getting operations endpoint
  - Fetching job details
  - Saving draft jobs
  - Publishing jobs
  - Getting company details
  - Fetching sub-users
  - Refreshing jobs

**Features:**
- Automatic retry on timeout (3 attempts, 2s+ exponential backoff)
- Proper error handling and logging
- Session management
- Response parsing

### 6. **job_poster.py** - Job Posting Orchestrator

**JobPoster Class:**
- Coordinates complete job posting workflow
- Initializes with company details and sub-users
- Builds job payloads for API
- Posts jobs individually or in bulk
- Handles validation and error reporting
- Supports concurrent job posting (thread pool)

**Key Methods:**
```python
initialize()                    # Load company info and users
prepare_job_payload(job)       # Build API request payload
post_job(job, action)          # Post single job
post_jobs_bulk(requests)       # Post multiple jobs concurrently
```

### 7. **utils.py** - Utilities

- **DataCleaner**: Clean strings, numbers, DataFrames
- **ResponseParser**: Parse API responses, extract job IDs, parse errors
- **FileManager**: Save/load CSV, JSON files
- **TimeUtils**: Timestamp utilities
- **ValidationUtils**: Email, URL, job ID validation

## Workflow

### Complete Flow

```
1. INITIALIZATION
   ├─ Setup logging
   ├─ Load configuration
   └─ Connect to database

2. FETCH JOBS
   ├─ Query database for jobs with status = ''
   ├─ Filter by company IDs (27117, 16987)
   └─ Load into DataFrame

3. PROCESS BY COMPANY
   ├─ Group jobs by company_id and job_type
   ├─ For each company:
   │  ├─ Initialize JobPoster
   │  ├─ Fetch company details
   │  ├─ Fetch sub-users
   │  └─ Prepare job requests

4. BUILD JOB OBJECTS
   ├─ Convert DataFrame rows to JobPostingRequest
   ├─ Parse experience strings
   ├─ Parse salary strings
   ├─ Parse keywords
   ├─ Build Job objects
   └─ Handle prediction for blank fields

5. APPLY BUSINESS LOGIC
   ├─ Validate job titles
   ├─ Validate keywords (min 3)
   ├─ Validate locations (max 3)
   ├─ Validate experience range
   ├─ Validate education requirements
   └─ Apply business rules

6. POST JOBS (BULK)
   ├─ Create ThreadPoolExecutor (max 5 workers)
   ├─ For each job:
   │  ├─ Prepare job payload
   │  ├─ Save draft (API call)
   │  ├─ Publish job (API call)
   │  ├─ Capture job ID
   │  └─ Update database
   └─ Wait for all to complete

7. RESULTS & REPORTING
   ├─ Aggregate results
   ├─ Calculate success rate
   ├─ Save results to CSV
   ├─ Generate summary
   └─ Log completion

```

## Usage

### Basic Usage

```python
from main import JobPostingAutomation
from config import TARGET_COMPANY_IDS, ACTION_SAVE

# Initialize automation
automation = JobPostingAutomation(
    cookies={'inauk_at': '...', 'inauk_rt': '...'},
    user_id='12345'
)

# Run with default companies
success = automation.run(
    company_ids=TARGET_COMPANY_IDS,
    action=ACTION_SAVE
)
```

### Advanced Usage

```python
# Custom company IDs
success = automation.run(
    company_ids=[27117, 16987, 9999],
    action=ACTION_UPDATE  # or ACTION_REFRESH, ACTION_REPOST
)

# Check results
summary = automation.generate_summary(results)
print(f"Success rate: {summary['success_rate']}%")
```

### Individual Job Posting

```python
from job_poster import JobPoster
from models import JobPostingRequest

poster = JobPoster(company_id='27117', user_id='12345', cookies=cookies)
poster.initialize()

request = JobPostingRequest(
    row_data={'title': 'Software Engineer', 'location': 'Bangalore'},
    job_id='202312312345',
    company_id='27117'
)

result = poster.post_job(job, action='SAVE')
print(f"Job posted: {result.new_job_id}")
```

## Data Models

### Job Model
```python
@dataclass
class Job:
    job_id: Optional[str]
    company_id: str
    company_name: str
    position: str
    description: str
    job_type: str  # 's', 'h', 'c'
    
    # Experience & Salary
    min_experience: int
    max_experience: int
    salary_detail: SalaryDetail
    
    # Locations
    national_locations: List[Location]
    international_locations: List[Location]
    
    # Education & Skills
    education: Education
    key_skills: Dict[str, Any]
    mandatory_keywords: Optional[List[str]]
    
    # Status & Assignment
    status: str
    assigned_sub_users: List[int]
    
    # Validation
    def validate(self) -> tuple[bool, List[str]]
```

### JobPostingResult
```python
@dataclass
class JobPostingResult:
    success: bool
    new_job_id: Optional[str]
    original_job_id: Optional[str]
    company_id: str
    message: str
    errors: List[str]
    warnings: List[str]
    posting_timestamp: Optional[datetime]
    posting_duration_ms: int
```

## Database Schema

### Jobs Table (jobs_for_posting)
```sql
SELECT * FROM dbo.jobs_for_posting 
WHERE [Company id] IN (27117, 16987)
AND [Job_Listing Status] = ''

-- Expected columns:
-- file, Company id, Job_Type, Source
-- title, description, JD, Position
-- Exp_Str, CTC_Str, Location_Str
-- Industry, Farea, Role
-- Keywords, UG, PG, Responses
```

## Error Handling

### Retry Logic
- Automatic retry on timeout/network errors
- Exponential backoff: 2s, 4s, 8s
- Max 3 attempts per API call

### Validation Errors
- Job title validation (length, characters)
- Keyword validation (count, format)
- Location validation (primary locations max 3)
- Experience validation (range checks)
- Education validation (course requirements)

### Error Reporting
- Detailed error logs with timestamps
- Error messages collected and reported
- Failed jobs saved to separate CSV
- Summary email with error details

## Logging

### Log Levels
- **INFO**: Normal operations, progress updates
- **WARNING**: Recoverable issues, retries
- **ERROR**: Failed operations, validation errors
- **DEBUG**: Detailed execution flow

### Log File
```
C:\logs\job_posting.log
```

### Console Output
All logs also appear in console for real-time monitoring.

## Configuration

### Key Settings (config.py)

```python
# Database
DB_SERVER = "naukrics\\sqlexpress"
DB_NAME = "manoj"

# API
API_TIMEOUT = 30  # seconds
API_RETRY_COUNT = 3
API_RETRY_DELAY = 2

# Target Companies
TARGET_COMPANY_IDS = [27117, 16987]

# Actions
ACTION_SAVE = "SAVE"
ACTION_UPDATE = "UPDATE"
ACTION_REFRESH = "REFRESH"
ACTION_REPOST = "REPOST"
```

## Requirements

```
pandas >= 1.0.0
pyodbc >= 4.0.0
requests >= 2.25.0
numpy >= 1.19.0
```

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Or install individually
pip install pandas pyodbc requests numpy
```

## Output Files

### Results
```
C:\a\job_posting_results_YYYYMMDD_HHMMSS.csv
```
Columns:
- company_id
- original_job_id
- new_job_id
- success (true/false)
- message
- errors (if any)
- duration_ms
- timestamp

### Error Log
```
C:\a\error_YYYYMMDD_HHMMSS.csv
```
Contains details of failed job postings.

### Database Status
```
C:\a\DB Status_YYYYMMDD_HHMMSS.csv
```
Status of database insertions.

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Check server name and credentials in config.py
   - Verify SQL Server is running
   - Check network connectivity

2. **API Timeout**
   - Increase API_TIMEOUT in config.py
   - Check internet connection
   - Reduce max_workers in bulk posting

3. **Job Validation Fails**
   - Check job title (max 70 chars)
   - Verify at least 3 keywords provided
   - Ensure 1-3 primary locations
   - Check experience range is valid

4. **Authentication Error**
   - Verify cookies are valid (not expired)
   - Refresh Microsoft authentication
   - Check user_id is correct

## Performance Tips

1. **Batch Processing**
   - Process jobs by company for better resource usage
   - Use bulk posting with ThreadPoolExecutor

2. **Concurrency**
   - Default max_workers = 5
   - Adjust based on API rate limits
   - Monitor server resources

3. **Database**
   - Create index on (Company id, Job_Listing Status)
   - Archive old logs regularly
   - Consider connection pooling

## Future Enhancements

- [ ] Support for additional job categories
- [ ] ML-based field prediction
- [ ] Real-time progress dashboard
- [ ] Email notifications on completion
- [ ] Slack integration for alerts
- [ ] Database backup before bulk operations
- [ ] Scheduled automation with cron

## Support

For issues or questions:
1. Check logs in C:\logs\job_posting.log
2. Review error CSV files
3. Verify configuration in config.py
4. Check database connectivity

## License

Internal use only - Naukri.com

## Version

v1.0.0 - Initial Release

---

**Last Updated**: August 2026
**Maintainer**: Abhishek Luthra
"# Automation-jobs-posting" 
"# Automation-jobs-posting" 
