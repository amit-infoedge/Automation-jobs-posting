# Quick Start Guide

## 5-Minute Setup

### Step 1: Install Dependencies
```bash
cd "C:\Data\repos\repos\NewPosting20240826\Posting\python code"
pip install -r requirements.txt
```

### Step 2: Configure Credentials
Edit `main.py` and add your authentication details:

```python
# In main.py, find the main() function:
cookies = {
    'inauk_at': 'your_microsoft_auth_token',
    'inauk_rt': 'your_refresh_token',
    # Add other cookies as needed
}
user_id = 'your_user_id'  # e.g., '123456'
```

### Step 3: Verify Configuration
Edit `config.py` to ensure:

```python
# Target companies
TARGET_COMPANY_IDS = [27117, 16987]

# Database
DB_SERVER = "naukrics\\sqlexpress"
DB_NAME = "manoj"
DB_USER = "ja"
```

### Step 4: Create Output Directories
```bash
mkdir C:\logs
mkdir C:\a
```

### Step 5: Test with Examples
```bash
python examples.py
```

Expected output:
```
[INFO] EXAMPLE 1: Validate Job
[INFO] Job valid: True
[INFO] Job validation passed!
...
[INFO] Examples completed
```

## Running the Automation

### Option 1: Run Immediately
```bash
python main.py
```

### Option 2: Run Specific Companies
Edit `main.py` and modify:
```python
success = automation.run(
    company_ids=[27117, 16987, 9999],  # Custom companies
    action=ACTION_SAVE  # or ACTION_UPDATE, ACTION_REFRESH
)
```

### Option 3: Schedule with Windows Task Scheduler
Create a batch file `run_automation.bat`:
```batch
@echo off
cd /d "C:\Data\repos\repos\NewPosting20240826\Posting\python code"
python main.py
```

Then schedule it:
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (daily, weekly, etc.)
4. Set action: `C:\run_automation.bat`

## What Gets Created

After running, check:

### Log File
```
C:\logs\job_posting.log
```

### Results File
```
C:\a\job_posting_results_YYYYMMDD_HHMMSS.csv
```

Contains:
- company_id
- original_job_id
- new_job_id
- success (true/false)
- message
- errors (if any)
- duration_ms
- timestamp

### Database Updates
- Jobs table updated with new job IDs
- Status changed to "Posted"
- Comments logged with any errors

## Common Tasks

### Post Jobs for Specific Company
```python
from main import JobPostingAutomation
from config import ACTION_SAVE

automation = JobPostingAutomation(cookies, user_id)
success = automation.run(company_ids=[27117], action=ACTION_SAVE)
```

### Validate a Job Before Posting
```python
from models import Job, Location, SalaryDetail

job = Job(
    company_id="27117",
    position="Software Engineer",
    description="...",
    # ... other fields
)

is_valid, errors = job.validate()
if not is_valid:
    print(f"Validation failed: {errors}")
```

### Parse Job Data
```python
from job_processor import JobProcessor

processor = JobProcessor()

# Parse experience
min_exp, max_exp = processor.parse_experience("3-8 years")

# Parse salary
min_sal, max_sal, currency = processor.parse_salary("8-12 LPA")

# Parse keywords
keywords = processor.parse_keywords("Python,Java*,SQL")
```

### Fetch Jobs from Database
```python
from database import DatabaseManager

db = DatabaseManager()
jobs_df = db.fetch_jobs_for_posting([27117, 16987])
print(f"Found {len(jobs_df)} jobs")
```

### Update Job Status Manually
```python
from database import DatabaseManager

db = DatabaseManager()
db.update_job_status('202312312345', 'Posted', 'Job posted successfully')
```

## Troubleshooting

### Database Connection Failed
**Error**: `Failed to connect to database`

**Solution**:
1. Verify SQL Server is running: `sqlcmd -S naukrics\sqlexpress -E`
2. Check username/password in `config.py`
3. Verify database exists: `SELECT name FROM sys.databases WHERE name='manoj'`

### API Timeout
**Error**: `[RETRY] Timeout on attempt 3/3`

**Solution**:
1. Increase `API_TIMEOUT` in `config.py`
2. Check internet connection
3. Try again later (server might be busy)
4. Reduce concurrent workers: `max_workers=2`

### Authentication Failed
**Error**: `Microsoft authentication failed`

**Solution**:
1. Refresh cookies: Clear and re-login on Naukri
2. Update `cookies` in `main.py` with fresh tokens
3. Check token expiry: Tokens expire in ~24 hours

### No Jobs Found
**Error**: `No jobs found for posting`

**Solution**:
1. Verify target companies in `config.py`
2. Check database: `SELECT COUNT(*) FROM jobs_for_posting WHERE [Company id] IN (27117, 16987) AND [Job_Listing Status] = ''`
3. Ensure jobs have status = '' (empty string)

### Validation Failed
**Error**: `Job Title cannot exceed 70 characters`

**Solution**:
- Edit data source to fix job titles
- Or implement custom field mapping in `job_processor.py`

## Monitoring

### Check Logs in Real-Time
```bash
# Windows PowerShell
Get-Content C:\logs\job_posting.log -Wait
```

### Count Successful Postings
```bash
# Count "Job posted" in log
Select-String "Job posted" C:\logs\job_posting.log | Measure-Object
```

### Check Results File
```python
import pandas as pd

results = pd.read_csv(r'C:\a\job_posting_results_YYYYMMDD_HHMMSS.csv')
print(f"Total: {len(results)}")
print(f"Successful: {results['success'].sum()}")
print(f"Failed: {(~results['success']).sum()}")
print(f"Success Rate: {results['success'].mean()*100:.1f}%")
```

## Important Notes

### Authentication Cookies
- Cookies expire after ~24 hours
- Refresh before long running operations
- Store securely (not in version control)

### Database Concurrency
- Single connection is used (safe for concurrent API calls)
- Connection auto-closes when DatabaseManager is deleted
- No need to manually close

### Job Validation
Mandatory fields:
- Position (1-70 chars)
- Description (non-empty)
- Min 3 keywords
- At least 1 location
- Max 3 primary locations
- Valid experience range
- Education requirements

### Rate Limiting
- Naukri API has rate limits
- Default: 5 concurrent jobs
- If errors: Reduce `max_workers` parameter
- Wait between batch runs

## Next Steps

1. ✅ Run `examples.py` to verify setup
2. ✅ Configure credentials
3. ✅ Run automation: `python main.py`
4. ✅ Monitor logs in `C:\logs\job_posting.log`
5. ✅ Check results in `C:\a\`
6. ✅ Schedule for automated runs

## Support

**Issues?** Check:
1. Log file: `C:\logs\job_posting.log`
2. Error CSV: `C:\a\error_YYYYMMDD_HHMMSS.csv`
3. README.md for detailed documentation
4. STRUCTURE.md for architecture details

**Contact**: abhishek.luthra@naukri.com

---

**Happy Job Posting! 🚀**
