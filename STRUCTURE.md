# Project Structure & Architecture

## Overview
This is a production-ready Python automation framework for job posting on Naukri platform, following enterprise-grade architecture with proper separation of concerns, strong typing, and comprehensive error handling.

## Directory Structure

```
Posting/python code/
├── config.py              # Configuration and constants
├── models.py              # Data models and domain objects
├── database.py            # Database layer (SQL operations)
├── job_processor.py       # Business logic and transformations
├── api_client.py          # Naukri API integration
├── job_poster.py          # Job posting orchestrator
├── utils.py               # Utility functions
├── main.py                # Entry point and main workflow
├── examples.py            # Usage examples
├── requirements.txt       # Python dependencies
├── README.md              # Full documentation
└── STRUCTURE.md           # This file
```

## Detailed File Descriptions

### 1. **config.py** (90 lines)
**Purpose**: Centralized configuration management

**Contents**:
- Database connection parameters
- API endpoints and timeouts
- Target company IDs (27117, 16987)
- Action types (SAVE, UPDATE, REFRESH, REPOST)
- File paths for data and logs
- Email configuration
- API retry parameters

**Key Constants**:
- `TARGET_COMPANY_IDS`: Companies to automate
- `API_TIMEOUT`: 30 seconds
- `API_RETRY_COUNT`: 3 attempts
- `DB_TABLE`: "jobs_for_posting"

---

### 2. **models.py** (280+ lines)
**Purpose**: Data model definitions using dataclasses

**Classes**:
- `Location`: Geographic location information
- `Education`: Education requirements
- `SalaryDetail`: Salary information
- `KeySkill`: Individual skill with preference flag
- `ResponseManagerSettings`: Email/URL response configuration
- `Job`: Complete job posting model with validation
- `JobPostingRequest`: Request wrapper for raw data
- `JobPostingResult`: Single job posting result
- `BulkPostingResult`: Bulk operation summary
- `SubUser`: Company sub-user representation
- `CompanyDetails`: Company information

**Features**:
- Type hints throughout
- Built-in validation methods
- Clean dataclass pattern
- Proper error handling

---

### 3. **database.py** (260 lines)
**Purpose**: Database connectivity and operations

**Classes**:
- `DatabaseConnection`: Low-level database operations
- `DatabaseManager`: Singleton pattern for connection management

**Key Methods**:
```python
connect()                           # Establish connection
fetch_jobs_for_posting(company_ids) # Query jobs from DB
update_job_status()                 # Update job posting status
insert_job_posting_result()         # Save posting results
log_posting_attempt()               # Log attempt details
check_job_exists_in_log()          # Duplicate check
execute_query()                     # Custom queries
fetch_query()                       # SELECT queries
```

**SQL Query Examples**:
- Fetch jobs with status filtering
- Update job_listing_status and comments
- Insert posting results
- Log posting attempts
- Check for duplicates in last 30 days

---

### 4. **job_processor.py** (450+ lines)
**Purpose**: Business logic and data transformation

**Classes**:

#### **JobValidator**
- `validate_title()`: Check title length (max 70), no invalid chars
- `validate_keywords()`: Verify keyword count (3-10)
- `validate_locations()`: Check location count (1-3 primary)
- `validate_experience()`: Validate min/max experience range
- `validate_education()`: Check education requirements

#### **JobProcessor**
- `parse_experience()`: Convert "2-5 years" → (2, 5)
- `parse_salary()`: Convert "10-20 LPA" → (1000000, 2000000)
- `parse_keywords()`: Convert "Python,Java*,SQL" → KeySkill objects
- `fill_blanks()`: Fill missing fields with defaults
- `apply_business_rules()`: Comprehensive validation
- `clean_jd()`: Remove buzzwords from description
- `predict_missing_fields()`: ML-like predictions from JD text

#### **JobBuilder**
- `build_from_request()`: Build complete Job object from raw data
- Handles all transformations and validations
- Provides detailed error reporting

---

### 5. **api_client.py** (350+ lines)
**Purpose**: Naukri API integration and HTTP communication

**Class**: `NaukriAPIClient`

**Features**:
- Retry decorator with exponential backoff
- Session management
- Automatic cookie handling
- Comprehensive error handling

**Key Methods**:
```python
get_operations()           # Get job creation endpoint
get_job_details()         # Fetch existing job
save_job_draft()          # Save as draft
publish_job()             # Publish from draft
get_company_details()     # Company information
get_sub_users()           # Sub-user list
refresh_jobs()            # Refresh multiple jobs
```

**Retry Logic**:
- 3 attempts max
- Exponential backoff: 2s, 4s, 8s
- Handles Timeout, ConnectionError, RequestException
- Detailed logging

---

### 6. **job_poster.py** (400+ lines)
**Purpose**: Job posting orchestration

**Class**: `JobPoster`

**Responsibilities**:
- Coordinate complete posting workflow
- Initialize with company details
- Build job payloads
- Post jobs (single and bulk)
- Handle concurrent operations
- Resource cleanup

**Key Methods**:
```python
initialize()               # Load company & users
prepare_job_payload()     # Build API request
post_job()                # Post single job
post_jobs_bulk()          # Post multiple (concurrent)
```

**Features**:
- ThreadPoolExecutor for concurrent posting
- Automatic validation
- Comprehensive error tracking
- Result aggregation
- Performance metrics

---

### 7. **utils.py** (300+ lines)
**Purpose**: Utility functions and helpers

**Classes**:
- `DataCleaner`: String/numeric cleaning, DataFrame operations
- `ResponseParser`: Parse API responses, extract job IDs, errors
- `FileManager`: Save/load CSV/JSON files
- `TimeUtils`: Timestamp, date utilities
- `ValidationUtils`: Email, URL, job ID validation

**Examples**:
```python
DataCleaner.clean_string()        # Strip, lowercase
DataCleaner.handle_encoding()     # Fix special chars
ResponseParser.extract_job_id()   # Parse redirect URL
FileManager.save_csv()            # Export results
TimeUtils.get_file_timestamp()    # File naming
ValidationUtils.is_valid_email()  # Validate email
```

---

### 8. **main.py** (350+ lines)
**Purpose**: Main automation orchestrator and entry point

**Class**: `JobPostingAutomation`

**Workflow**:
1. Setup logging
2. Fetch jobs from database
3. Group by company
4. Initialize posting for each company
5. Build job objects
6. Apply business logic
7. Post jobs (bulk with concurrency)
8. Save results to CSV
9. Generate summary
10. Log completion

**Key Methods**:
```python
run()                  # Main automation entry point
fetch_jobs_from_db()  # Query database
process_company_jobs()# Handle company batch
save_results()        # Export to CSV
generate_summary()    # Create report
```

**Output Files**:
- `job_posting_results_YYYYMMDD_HHMMSS.csv`
- `job_posting.log`

---

### 9. **examples.py** (450+ lines)
**Purpose**: Usage examples demonstrating all features

**Examples**:
1. Validate job object
2. Parse experience/salary strings
3. Validate keywords
4. Fetch jobs from database
5. Build job from raw data
6. Apply business rules
7. Post single job
8. Clean and transform data
9. Validate required fields
10. Time utilities

**Usage**:
```bash
python examples.py
```

---

### 10. **requirements.txt** (20 lines)
**Purpose**: Python package dependencies

**Packages**:
- pandas >= 1.3.0
- numpy >= 1.21.0
- pyodbc >= 4.0.0
- requests >= 2.26.0
- openpyxl >= 3.6.0
- python-dateutil >= 2.8.2

**Installation**:
```bash
pip install -r requirements.txt
```

---

### 11. **README.md** (600+ lines)
**Purpose**: Comprehensive documentation

**Sections**:
- Overview and features
- Architecture explanation
- Component descriptions
- Complete workflow diagram
- Usage examples (basic and advanced)
- Data models reference
- Database schema
- Error handling
- Configuration guide
- Logging setup
- Output files
- Troubleshooting
- Performance optimization

---

## Data Flow

### Complete Job Posting Flow

```
SQL Database
    ↓
fetch_jobs_for_posting()
    ↓
DataFrame with raw job data
    ↓
Group by Company ID
    ↓
For each Company:
    ├─ Initialize JobPoster
    ├─ Get Company Details
    ├─ Get Sub-users
    └─ Process Jobs
        ↓
    For each Job Row:
        ├─ Create JobPostingRequest
        ├─ Build Job object (JobBuilder)
        ├─ Parse fields (JobProcessor)
        ├─ Validate (JobValidator)
        └─ Apply Business Rules
            ↓
        Prepare Job Payload
            ↓
        API: Save Draft (api_client)
            ↓
        API: Publish Job (api_client)
            ↓
        Capture Job ID (ResponseParser)
            ↓
        Update Database
            ↓
        Create JobPostingResult
        ↓
    Aggregate Results (BulkPostingResult)
    ↓
Save Results CSV
    ↓
Generate Summary
    ↓
Log Completion
```

## Class Relationships

```
┌─────────────────────────────────────────┐
│        JobPostingAutomation             │
│         (Entry Point)                   │
└──────────┬──────────────────────────────┘
           │
           ├─→ DatabaseManager
           │   └─→ DatabaseConnection
           │
           ├─→ JobPoster (per company)
           │   ├─→ NaukriAPIClient
           │   ├─→ JobProcessor
           │   └─→ JobBuilder
           │
           └─→ Utilities
               ├─→ DataCleaner
               ├─→ ResponseParser
               ├─→ FileManager
               └─→ ValidationUtils
```

## Configuration Hierarchy

```
config.py (Global Configuration)
    ↓
    ├─ Database config
    ├─ API config
    ├─ Target companies
    ├─ Output directories
    └─ Email settings
        ↓
    DatabaseConnection
    NaukriAPIClient
    JobPostingAutomation
```

## Error Handling Strategy

```
API Level (api_client.py)
    └─→ @retry_on_exception decorator
        ├─ Timeout handling (3 retries)
        ├─ Connection error handling
        └─ Response parsing

Job Level (job_poster.py)
    └─→ Try-catch in post_job()
        ├─ Validation errors
        ├─ API errors
        └─ Result tracking

Automation Level (main.py)
    └─→ Try-catch in run()
        ├─ Database errors
        ├─ Company processing errors
        └─ Overall summary

Logging Level
    └─→ All errors logged
        ├─ File: C:\logs\job_posting.log
        └─ Console output
```

## Testing Strategy

Test with `examples.py`:
```bash
python examples.py  # Runs all 10 examples
```

Individual tests:
```python
# Test 1: Validation
from examples import example_validate_job
example_validate_job()

# Test 2: Data parsing
from examples import example_parse_job_data
example_parse_job_data()

# Test 3: Database
from examples import example_fetch_jobs
example_fetch_jobs()
```

## Deployment Checklist

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Configure credentials in `config.py`
- [ ] Set authentication cookies in `main.py`
- [ ] Create log directory: `C:\logs\`
- [ ] Create output directory: `C:\a\`
- [ ] Test database connection
- [ ] Run examples to verify setup
- [ ] Configure scheduled task if needed
- [ ] Set up email notifications (optional)
- [ ] Monitor first run logs

## Key Features Implemented

✓ Database integration (SQL Server)
✓ Multi-company support (concurrent)
✓ Comprehensive data validation
✓ Business rule engine
✓ API integration with retry logic
✓ Bulk job posting (ThreadPoolExecutor)
✓ Field prediction/auto-fill
✓ Error tracking and reporting
✓ CSV export of results
✓ Detailed logging
✓ Modular architecture
✓ Type hints throughout
✓ Exception handling
✓ Resource cleanup

## Performance Metrics

- **Concurrent Jobs**: 5 parallel (configurable)
- **API Timeout**: 30 seconds (configurable)
- **Retry Attempts**: 3 with exponential backoff
- **Database**: Single connection with cursor reuse
- **Memory**: Efficient DataFrame operations
- **Logging**: Async file writes

## Future Enhancements

- [ ] Dashboard/web UI
- [ ] Scheduled automation (APScheduler)
- [ ] Email notifications (smtplib)
- [ ] Slack integration
- [ ] Advanced field prediction (ML)
- [ ] Batch import from Excel
- [ ] Job update/refresh support
- [ ] Analytics and reporting

---

**Version**: 1.0.0  
**Created**: August 2026  
**Python**: 3.8+  
**Platform**: Windows (SQL Server + Naukri API)
