"""
Configuration and Constants for Job Posting Automation
"""

import os
import base64

# Database Configuration
DB_DRIVER = "SQL Server"
DB_SERVER = "naukrics\\sqlexpress"
DB_NAME = "manoj"
DB_USER = "ja"
DB_PASSWORD = base64.b64decode(bytes(b'amFAMjAxMQ==')).decode("utf-8")

# API Configuration
API_TIMEOUT = 30  # seconds
API_RETRY_COUNT = 3
API_RETRY_DELAY = 2  # seconds

# Naukri API Endpoints
NAUKRI_BASE_URL = "https://jpoffline.naukri.com"
OPERATIONS_API = f"{NAUKRI_BASE_URL}/cloudgateway-jobposting/jplite-rm-services/v0/operations"
JOB_POSTING_API = f"{NAUKRI_BASE_URL}/cloudgateway-jobposting/job-services/v1/job/draftsave"
PUBLISH_JOB_API = f"{NAUKRI_BASE_URL}/cloudgateway-jobposting/job-services/v1/publish/job"
GET_JOB_API = f"{NAUKRI_BASE_URL}/cloudgateway-jobposting/job-services/v1/job"
COMPANY_DETAILS_API = f"{NAUKRI_BASE_URL}/cloudgateway-mnr/company-services/v0/companies"
SUB_USERS_API = f"{NAUKRI_BASE_URL}/cloudgateway-mnr/company-services/v0/company/getSubUserList"
# Auto-forward email endpoints (ORE.cs GetEmail line 301, AddEmail line 263)
COMPANY_EMAILS_API = f"{NAUKRI_BASE_URL}/cloudgateway-mnr/company-services/v0/companies"
ADD_EMAIL_API = f"{NAUKRI_BASE_URL}/cloudgateway-mnr/company-services/v0/email"

# Cookie Authentication API
COOKIE_API_ENDPOINT = "https://dashboard.infoedge.com:8282/common/v1/logins?name=offline"
COOKIE_API_USERNAME = "automation"
COOKIE_API_PASSWORD = None  # Not required for this endpoint

# Default headers for API calls
DEFAULT_HEADERS = {
    'SystemId': 'naukriIndia',
    'AppId': "4",
    'gid': "LOCATION,INDUSTRY,EDUCATION,FAREA_ROLE,KEYSKILLS",
    'content-type': 'application/json'
}

# Excel/Data file paths
LOCATION_MAPPING_FILE = r"c:\imp\loc mapping.xlsx"
LOCATION_MAPPING_SHEET = "loc"
INDUSTRY_FAREA_ROLE_FILE = r"C:\Files\ind-farea-role.xlsx"
INDUSTRY_SHEET = "ind1"
FAREA_SHEET = "farea"
ROLE_SHEET = "role"

# Output directory
OUTPUT_DIR = r"C:\a"

# Target Company IDs for automation
# TARGET_COMPANY_IDS = [16987]
TARGET_COMPANY_IDS = [16987,27117]

# Job Posting Actions
ACTION_SAVE = "SAVE"
ACTION_UPDATE = "UPDATE"
ACTION_REFRESH = "REFRESH"
ACTION_REPOST = "REPOST"

# Database table names
JOBS_TABLE = "jobs_for_posting"
LOG_TABLE = "RRR_log"
# Per-company junk phrases stripped from the JD (RibbonController.cs:115)
JUNK_TABLE = "crawler.junk"
JUNK_PROCESS = "offline"

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = r"C:\logs\job_posting.log"

# Email Configuration
EMAIL_ON_COMPLETION = True
EMAIL_RECIPIENTS = ["amit.k13@naukri.com"]
EMAIL_CC = ["abhishek.luthra@naukri.com", "gaurav.2@naukri.com"]
