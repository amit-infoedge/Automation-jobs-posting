"""
Test script to verify payload structure matches postjob1.py requirements
"""

import json
from job_poster import JobPoster
from models import Job, Location, SalaryDetail, Education, ResponseManagerSettings

# Create a test job
test_job = Job()
test_job.job_id = "TEST123"
test_job.company_id = "27117"
test_job.company_name = "Test Company"
test_job.position = "Senior Software Engineer"
test_job.description = "<p>We are looking for a Senior Software Engineer with 5+ years of experience</p>"
test_job.job_type = "h"
test_job.min_experience = 5
test_job.max_experience = 10
test_job.salary_detail = SalaryDetail(minimum_salary=10, maximum_salary=20, currency="LPA")
test_job.national_locations = [Location(location_id="1", location_name="Bangalore", is_custom_group=False)]
test_job.international_locations = []
test_job.key_skills = {"Python": {"label": "Python", "preferred": True}, "Java": {"label": "Java", "preferred": False}}
test_job.industry_gid = "1"
test_job.functional_area_gid = "1"
test_job.job_role_gid = "1"
test_job.role_category_gid = "1"
test_job.education = Education(ug_gid=["#9502:"], pg_gid=[], ppg_gid=[])
test_job.response_manager_settings = ResponseManagerSettings(
    response_manager_type='email',
    emails=['test@example.com'],
    frequency='On every new apply',
    company_url=None,
    subject_settings={}
)

# Create poster
poster = JobPoster("27117", "12345", {}, test_mode=True)

# Get payload
draft_payload, publish_payload = poster.prepare_job_payload(test_job, "SAVE")

print("=" * 80)
print("DRAFT PAYLOAD STRUCTURE")
print("=" * 80)
print(json.dumps(draft_payload, indent=2, default=str)[:2000])

print("\n" + "=" * 80)
print("PUBLISH PAYLOAD STRUCTURE")
print("=" * 80)
print(json.dumps(publish_payload, indent=2, default=str)[:2000])

print("\n" + "=" * 80)
print("KEY FIELDS CHECK")
print("=" * 80)

# Check draft payload structure
draft_keys = set(draft_payload.keys())
expected_draft_keys = {'primaryKey', 'draftName', 'secondaryKey', 'tertiaryKey', 'id', 'boards', 'job'}
print(f"Draft payload has all primary keys: {expected_draft_keys.issubset(draft_keys)}")
print(f"Missing keys: {expected_draft_keys - draft_keys}")

# Check job payload structure
job_payload = draft_payload.get('job', {})
job_keys = set(job_payload.keys())
critical_keys = {'title', 'description', 'companyDetail', 'registrationType', 'responseManager',
                 'industryGid', 'functionalAreaGid', 'jobRoleGid', 'roleCategoryGid',
                 'nationalLocationsGid', 'education', 'salaryDetail', 'category'}
print(f"Job payload has all critical keys: {critical_keys.issubset(job_keys)}")
print(f"Missing critical keys: {critical_keys - job_keys}")

# Check companyDetail fields
company_detail = job_payload.get('companyDetail', {})
print(f"\nCompany Detail fields:")
print(f"  - name: {company_detail.get('name')}")
print(f"  - details: {len(str(company_detail.get('details', ''))) if company_detail.get('details') else 0} chars")
print(f"  - address: {company_detail.get('address')}")

# Check response manager
print(f"\nResponse Manager: {job_payload.get('responseManager')}")
print(f"Response Manager Settings: {job_payload.get('responseManagerSettings')}")

print("\n✓ Payload structure validation complete")
