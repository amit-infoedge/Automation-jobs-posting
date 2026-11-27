"""
SQL to API Payload Mapping - Active Implementation
Automatically maps database columns to Naukri API request fields
Used during job posting to transform SQL rows into API payloads
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
import re

logger = logging.getLogger(__name__)


class ColumnMapping:
    """Maps a single SQL column to API field(s)"""

    def __init__(self, api_path: str, col_type: str = 'string', required: bool = False,
                 transform_func=None, default: Any = None, valid_values: List = None):
        """
        Initialize column mapping

        Args:
            api_path: Dot-notation path in API payload (e.g., 'job.title')
            col_type: Data type (string, int, float, bool)
            required: Whether column is mandatory
            transform_func: Function to transform value before sending to API
            default: Default value if not provided
            valid_values: List of allowed values
        """
        self.api_path = api_path
        self.col_type = col_type
        self.required = required
        self.transform_func = transform_func
        self.default = default
        self.valid_values = valid_values or []

    def transform(self, value: Any) -> Any:
        """Transform value for API"""
        if value is None or value == '':
            return self.default

        if self.transform_func:
            try:
                return self.transform_func(value)
            except Exception as e:
                logger.error(f"Error transforming value '{value}': {str(e)}")
                return self.default

        return value

    def validate(self, value: Any) -> Tuple[bool, Optional[str]]:
        """Validate value"""
        if value is None or value == '':
            if self.required:
                return False, "Required field missing"
            return True, None

        if self.valid_values and value not in self.valid_values:
            return False, f"Invalid value. Must be one of: {self.valid_values}"

        return True, None


class SQLToAPIMapping:
    """Maps SQL table columns to Naukri API request fields"""

    # Define all column mappings - mapped from actual SQL table schema
    MAPPINGS = {
        # Identity & Basic Info (from jobs_for_posting table)
        'Sr No': ColumnMapping('data.Sr No', 'int', required=False),
        'Company id': ColumnMapping('job.companyId', 'int', required=True,
                                  transform_func=lambda x: str(int(float(x)))),
        'Company Name': ColumnMapping('job.companyDetail.name', 'string', required=False),
        'Posting Type': ColumnMapping('job.category', 'string', required=True,
                                    valid_values=['s', 'h', 'c']),

        # Job Details - Title & Description
        'Position': ColumnMapping('job.title', 'string', required=True),
        'Job Description': ColumnMapping('job.rnr', 'string', required=False),  # For C-type jobs
        'JD': ColumnMapping('job.description', 'string', required=False),  # For H/S-type jobs
        'Candidate Profile': ColumnMapping('job.dcp', 'string', required=False),  # Desired Candidate Profile

        # Experience (from Exp column - needs parsing)
        'Exp': ColumnMapping('job.minimumExperience,job.maximumExperience', 'string', required=False),

        # Salary (from CTC column - needs parsing)
        'CTC': ColumnMapping('job.salaryDetail', 'string', required=False),

        # Keywords & Skills
        'KeyWords': ColumnMapping('job.keySkillsGid', 'string', required=False),
        'Mandaory Keywords': ColumnMapping('job.keySkillsGid', 'string', required=False),

        # Location
        'Location': ColumnMapping('job.nationalLocationsGid', 'string', required=True),
        'Shared_Location': ColumnMapping('job.otherNationalLocations', 'string', required=False),

        # Categories & Industry
        'Industry': ColumnMapping('job.industryGid', 'string', required=False),
        'Functional Area': ColumnMapping('job.functionalAreaGid', 'string', required=False),
        'Role': ColumnMapping('job.jobRoleGid', 'string', required=False),

        # Education
        'UG': ColumnMapping('job.education.ugGid', 'string', required=False, default='#9502:'),
        'PG': ColumnMapping('job.education.pgGid', 'string', required=False, default='#9511:'),
        'PPG': ColumnMapping('job.education.ppgGid', 'string', required=False),
        'Qualification': ColumnMapping('job.qualification', 'string', required=False),

        # Response Management
        'Responses': ColumnMapping('job.responseManager', 'string', required=False,
                                 valid_values=['email', 'url', 'rms']),
        'Recruiter Email': ColumnMapping('job.responseManagerSettings.emails', 'string', required=False),
        'URL': ColumnMapping('job.responseManagerSettings.companyUrl', 'string', required=False),

        # Company Information
        'Company_Profile': ColumnMapping('job.companyDetail.details', 'string', required=False),

        # Sub-users & Assignment
        'Assign To Executive': ColumnMapping('job.assignedSubUsers', 'string', required=False),

        # Metadata & Status
        'Source': ColumnMapping('data.Source', 'string', required=False),
        'Process': ColumnMapping('data.Process', 'string', required=False),
        'Added By': ColumnMapping('data.Added By', 'string', required=False, default='Automation'),
        'Added Date': ColumnMapping('data.Added Date', 'datetime', required=False),
        'Unique Sr No': ColumnMapping('data.Unique Sr No', 'int', required=False),
        'Resurgence_Type': ColumnMapping('data.Resurgence_Type', 'string', required=False),
        'Executive Name': ColumnMapping('data.Executive Name', 'string', required=False),
        'Executive Status': ColumnMapping('data.Executive Status', 'string', required=False),
        'Blanket': ColumnMapping('data.Blanket', 'string', required=False),
        'Approved Source': ColumnMapping('data.Approved Source', 'string', required=False),

        # Status tracking columns (updated after posting)
        'Job_Listing Status': ColumnMapping('data.Job_Listing Status', 'string', required=False),
        'Job_Listing Updation_Date': ColumnMapping('data.Job_Listing Updation_Date', 'datetime', required=False),
        'Job Id': ColumnMapping('data.Job Id', 'string', required=False),
        'Job_Listing Comments': ColumnMapping('data.Job_Listing Comments', 'string', required=False),
        'Job_posting_Status': ColumnMapping('data.Job_posting_Status', 'string', required=False),

        # Additional metadata
        'Recruiter Link': ColumnMapping('data.Recruiter Link', 'string', required=False),
        'Priority': ColumnMapping('data.Priority', 'string', required=False),
        'Team Comments': ColumnMapping('data.Team Comments', 'string', required=False),
    }

    @staticmethod
    def get_mapping(column_name: str) -> Optional[ColumnMapping]:
        """Get mapping for a column"""
        return SQLToAPIMapping.MAPPINGS.get(column_name)

    @staticmethod
    def get_all_mappings() -> Dict[str, ColumnMapping]:
        """Get all mappings"""
        return SQLToAPIMapping.MAPPINGS

    @staticmethod
    def get_required_columns() -> List[str]:
        """Get list of required columns"""
        return [col for col, mapping in SQLToAPIMapping.MAPPINGS.items() if mapping.required]

    @staticmethod
    def get_optional_columns() -> List[str]:
        """Get list of optional columns"""
        return [col for col, mapping in SQLToAPIMapping.MAPPINGS.items() if not mapping.required]

    @staticmethod
    def validate_row(row: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate if row has all required columns

        Args:
            row: Database row

        Returns:
            (is_valid, error_list)
        """
        errors = []

        for col_name, mapping in SQLToAPIMapping.MAPPINGS.items():
            if mapping.required and col_name not in row:
                errors.append(f"Missing required column: {col_name}")

        return len(errors) == 0, errors


class PayloadBuilder:
    """Builds API payload from SQL row"""

    def __init__(self):
        self.mapping = SQLToAPIMapping()

    def build(self, row: Dict[str, Any], job_type: str = 'h', action: str = 'SAVE') -> Dict[str, Any]:
        """
        Build complete API payload from SQL row

        Args:
            row: Dictionary with SQL column values
            job_type: Job type (s, h, c)
            action: Action type (SAVE, UPDATE, REFRESH, REPOST)

        Returns:
            Complete API payload
        """
        payload = {
            'job': {
                'createdDate': int(__import__('time').time() * 1000),
                'jobState': action,
                'mode': 'jp',
                'jobId': None,
                'draftId': None,
                'source': 'offline',
                'jobType': 'fulltime',
                'companyType': 'established',
            },
            'data': {},
            'boards': {
                '1': {
                    'responseManager': 'email'
                }
            }
        }

        # Validate row
        is_valid, errors = self.mapping.validate_row(row)
        if not is_valid:
            logger.error(f"Row validation failed: {errors}")
            return {'error': errors}

        # Transform each column
        for col_name, col_value in row.items():
            mapping = self.mapping.get_mapping(col_name)
            if not mapping:
                continue

            # Validate
            valid, error = mapping.validate(col_value)
            if not valid:
                logger.warning(f"Column {col_name} validation failed: {error}")
                continue

            # Transform
            transformed_value = mapping.transform(col_value)

            # Special handling for composite fields
            if col_name == 'Exp_Str' and transformed_value:
                # Parse "3-5 years" format
                min_exp, max_exp = self._parse_experience(transformed_value)
                if min_exp and max_exp:
                    self._set_nested_value(payload, 'job.minimumExperience', str(min_exp))
                    self._set_nested_value(payload, 'job.maximumExperience', str(max_exp))
                continue

            if col_name == 'CTC_Str' and transformed_value:
                # Parse "10-20 LPA" format
                min_sal, max_sal = self._parse_salary(transformed_value)
                if min_sal and max_sal:
                    self._set_nested_value(payload, 'job.salaryDetail.minimumSalary', int(min_sal))
                    self._set_nested_value(payload, 'job.salaryDetail.maximumSalary', int(max_sal))
                    self._set_nested_value(payload, 'job.salaryDetail.currency', 'INR')
                continue

            if col_name == 'Keywords' and transformed_value:
                # Convert comma-separated to dict with preferred flag
                skills_dict = self._parse_keywords(transformed_value)
                self._set_nested_value(payload, 'job.keySkillsGid', skills_dict)
                continue

            if col_name == 'subuser' and transformed_value:
                # Parse semicolon-separated subusers
                subuser_list = [u.strip() for u in str(transformed_value).split(';') if u.strip()]
                self._set_nested_value(payload, 'job.assignedSubUsers', subuser_list)
                continue

            # Handle normal fields
            api_path = mapping.api_path
            if ',' not in api_path:  # Single path
                self._set_nested_value(payload, api_path, transformed_value)

        # Job-type specific settings
        if job_type == 's':
            payload['job']['freeJob'] = 1
            payload['job']['subCategoryType'] = 'basic'
        elif job_type == 'c':
            payload['job']['rolesAndResponsibilities'] = row.get('rnr', '')
            payload['job']['desiredCandidateProfile'] = row.get('dcp', '')
            payload['job']['perksAndBenefits'] = row.get('jpb', '')

        return payload

    @staticmethod
    def _parse_experience(exp_str: str) -> Tuple[Optional[int], Optional[int]]:
        """Parse experience string like '3-5 years'"""
        try:
            numbers = re.findall(r'\d+', str(exp_str))
            if len(numbers) >= 2:
                return int(numbers[0]), int(numbers[1])
            elif len(numbers) == 1:
                min_val = int(numbers[0])
                max_val = min_val + 5 if min_val < 10 else min_val + 10
                return min_val, max_val
        except Exception as e:
            logger.error(f"Error parsing experience: {str(e)}")
        return None, None

    @staticmethod
    def _parse_salary(salary_str: str) -> Tuple[Optional[float], Optional[float]]:
        """Parse salary string like '10-20 LPA'"""
        try:
            salary_str = str(salary_str).replace('Rs.', '').replace('rs.', '').upper()
            numbers = re.findall(r'[\d.]+', salary_str)

            if len(numbers) >= 2:
                min_sal = float(numbers[0])
                max_sal = float(numbers[1])

                # Convert LPA to actual salary
                if min_sal < 101:
                    min_sal *= 100000
                if max_sal < 101:
                    max_sal *= 100000

                return min_sal, max_sal
        except Exception as e:
            logger.error(f"Error parsing salary: {str(e)}")
        return None, None

    @staticmethod
    def _parse_keywords(keywords_str: str) -> Dict[str, Dict[str, Any]]:
        """Parse keyword string 'Python,Java*,SQL'"""
        skills = {}
        try:
            for keyword in str(keywords_str).split(','):
                keyword = keyword.strip()
                is_mandatory = False

                if keyword.endswith('*'):
                    keyword = keyword.rstrip('*').strip()
                    is_mandatory = True

                if keyword:
                    skills[keyword] = {
                        'label': keyword,
                        'preferred': is_mandatory
                    }
        except Exception as e:
            logger.error(f"Error parsing keywords: {str(e)}")

        return skills

    @staticmethod
    def _set_nested_value(obj: Dict, path: str, value: Any):
        """Set value in nested dict using dot notation (job.title -> obj['job']['title'])"""
        paths = path.split('.')
        current = obj

        for key in paths[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[paths[-1]] = value


class MappingValidator:
    """Validates mappings and reports issues"""

    @staticmethod
    def validate_job_data(row: Dict[str, Any], job_type: str = 'h') -> Tuple[bool, List[str]]:
        """
        Validate job data for posting

        Args:
            row: Job data from database
            job_type: Job type (s, h, c)

        Returns:
            (is_valid, error_list)
        """
        errors = []

        # Required fields for all job types
        required_fields = ['file', 'Company id', 'Job_Type', 'title', 'Location_Str']

        for field in required_fields:
            if field not in row or not row[field]:
                errors.append(f"Missing required field: {field}")

        # Job type specific validation
        if job_type == 'c':
            if 'rnr' not in row or not row.get('rnr'):
                errors.append("For C-type jobs, 'rnr' (Roles & Responsibilities) is required")

        # Validate title length
        if 'title' in row:
            title = str(row['title'])
            if len(title) > 70:
                errors.append(f"Job title too long ({len(title)} chars, max 70)")

        # Validate experience if provided
        if 'minExp' in row and 'maxExp' in row:
            try:
                min_exp = int(float(str(row.get('minExp', 0))))
                max_exp = int(float(str(row.get('maxExp', 0))))
                if min_exp > max_exp:
                    errors.append(f"Invalid experience range: min ({min_exp}) > max ({max_exp})")
            except ValueError:
                errors.append("Experience values must be numeric")

        return len(errors) == 0, errors
