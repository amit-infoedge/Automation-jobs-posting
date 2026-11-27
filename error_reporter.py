"""
Error Reporting and Excel Generation Module
Generates detailed error reports for failed job postings
"""

import pandas as pd
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from job_validator_advanced import ValidationError

logger = logging.getLogger(__name__)


class JobPostingError:
    """Represents an error in job posting"""

    def __init__(self, job_id: str, job_title: str = "", company_id: str = "",
                 error_type: str = "", error_message: str = "", status: str = "FAILED"):
        """
        Initialize job posting error

        Args:
            job_id: Job ID that failed
            job_title: Job title
            company_id: Company ID
            error_type: Type of error (VALIDATION, AUTHENTICATION, API, DATABASE, etc.)
            error_message: Detailed error message
            status: Status (FAILED, PENDING_REVIEW, etc.)
        """
        self.job_id = job_id
        self.job_title = job_title
        self.company_id = company_id
        self.error_type = error_type
        self.error_message = error_message
        self.status = status
        self.timestamp = datetime.now()
        self.resolution = ""  # For manual resolution notes

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DataFrame"""
        return {
            'Job ID': self.job_id,
            'Job Title': self.job_title,
            'Company ID': self.company_id,
            'Error Type': self.error_type,
            'Error Message': self.error_message,
            'Status': self.status,
            'Timestamp': self.timestamp.isoformat(),
            'Resolution': self.resolution
        }


class ValidationErrorReporter:
    """Reports validation errors in structured format"""

    @staticmethod
    def create_validation_error(job_id: str, job_title: str, company_id: str,
                               validation_errors: List[ValidationError]) -> JobPostingError:
        """
        Create a JobPostingError from validation errors

        Args:
            job_id: Job ID
            job_title: Job title
            company_id: Company ID
            validation_errors: List of ValidationError objects

        Returns:
            JobPostingError instance
        """
        # Group errors by field
        errors_by_field = {}
        critical_count = 0

        for error in validation_errors:
            if error.field not in errors_by_field:
                errors_by_field[error.field] = []
            errors_by_field[error.field].append(error.message)

            if error.severity == "error":
                critical_count += 1

        # Create summary message
        error_parts = []
        for field, messages in errors_by_field.items():
            field_errors = "; ".join(messages)
            error_parts.append(f"[{field}] {field_errors}")

        error_message = " | ".join(error_parts)

        return JobPostingError(
            job_id=job_id,
            job_title=job_title,
            company_id=company_id,
            error_type="VALIDATION_ERROR",
            error_message=error_message,
            status="FAILED"
        )


class AuthenticationErrorReporter:
    """Reports authentication errors"""

    @staticmethod
    def create_cookie_error(error_code: str, error_message: str) -> JobPostingError:
        """
        Create error for cookie/authentication issues

        Args:
            error_code: Error code (COOKIE_INVALID, COOKIE_EXPIRED, etc.)
            error_message: Error message

        Returns:
            JobPostingError instance
        """
        return JobPostingError(
            job_id="N/A",
            job_title="N/A",
            company_id="N/A",
            error_type="AUTHENTICATION_ERROR",
            error_message=f"[{error_code}] {error_message}",
            status="BLOCKED"
        )


class ErrorReportGenerator:
    """Generates error reports in Excel format"""

    def __init__(self, output_file: str = None):
        """
        Initialize report generator

        Args:
            output_file: Output Excel file path
        """
        self.output_file = output_file or f"job_posting_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        self.errors = []

    def add_error(self, error: JobPostingError):
        """Add an error to the report"""
        self.errors.append(error)
        logger.info(f"Added error for job {error.job_id}: {error.error_type}")

    def add_errors(self, errors: List[JobPostingError]):
        """Add multiple errors to the report"""
        for error in errors:
            self.add_error(error)

    def generate_report(self) -> str:
        """
        Generate Excel report with error details

        Returns:
            Path to generated Excel file
        """
        try:
            if not self.errors:
                logger.warning("No errors to report")
                return None

            # Convert errors to dictionaries
            error_dicts = [error.to_dict() for error in self.errors]

            # Create DataFrame
            df = pd.DataFrame(error_dicts)

            # Reorder columns
            column_order = [
                'Job ID', 'Job Title', 'Company ID', 'Error Type',
                'Error Message', 'Status', 'Timestamp', 'Resolution'
            ]
            df = df[[col for col in column_order if col in df.columns]]

            # Create Excel writer
            with pd.ExcelWriter(self.output_file, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Errors', index=False)

                # Format Excel
                worksheet = writer.sheets['Errors']

                # Auto-adjust column widths
                for column in worksheet.columns:
                    max_length = 0
                    column = [cell for cell in column]
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = (max_length + 2)
                    worksheet.column_dimensions[column[0].column_letter].width = adjusted_width

                # Add summary sheet
                self._add_summary_sheet(writer, df)

            logger.info(f"Error report generated: {self.output_file}")
            return self.output_file

        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            return None

    def _add_summary_sheet(self, writer, df: pd.DataFrame):
        """Add summary information to Excel"""
        try:
            # Summary statistics
            summary_data = {
                'Metric': [
                    'Total Errors',
                    'Validation Errors',
                    'Authentication Errors',
                    'API Errors',
                    'Database Errors',
                    'Other Errors'
                ],
                'Count': [
                    len(df),
                    len(df[df['Error Type'] == 'VALIDATION_ERROR']),
                    len(df[df['Error Type'] == 'AUTHENTICATION_ERROR']),
                    len(df[df['Error Type'] == 'API_ERROR']),
                    len(df[df['Error Type'] == 'DATABASE_ERROR']),
                    len(df[df['Error Type'].isin(['VALIDATION_ERROR', 'AUTHENTICATION_ERROR', 'API_ERROR', 'DATABASE_ERROR'])  == False])
                ]
            }

            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

        except Exception as e:
            logger.warning(f"Could not add summary sheet: {str(e)}")

    def get_error_count(self) -> int:
        """Get total error count"""
        return len(self.errors)

    def get_errors_by_type(self) -> Dict[str, int]:
        """Get count of errors by type"""
        counts = {}
        for error in self.errors:
            counts[error.error_type] = counts.get(error.error_type, 0) + 1
        return counts


class BulkErrorReporter:
    """Reports on bulk job posting results"""

    def __init__(self, output_file: str = None):
        """
        Initialize bulk reporter

        Args:
            output_file: Output Excel file path
        """
        self.output_file = output_file or f"job_posting_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        self.successful_jobs = []
        self.failed_jobs = []

    def add_successful_job(self, job_data: Dict[str, Any]):
        """Add successful job posting"""
        job_data['Status'] = 'POSTED'
        job_data['Timestamp'] = datetime.now().isoformat()
        self.successful_jobs.append(job_data)

    def add_failed_job(self, job_data: Dict[str, Any], error: JobPostingError):
        """Add failed job posting"""
        job_data['Status'] = error.status
        job_data['Error'] = error.error_message
        job_data['Error Type'] = error.error_type
        job_data['Timestamp'] = datetime.now().isoformat()
        self.failed_jobs.append(job_data)

    def generate_report(self) -> str:
        """
        Generate comprehensive Excel report

        Returns:
            Path to generated Excel file
        """
        try:
            with pd.ExcelWriter(self.output_file, engine='openpyxl') as writer:
                # Successful jobs sheet
                if self.successful_jobs:
                    df_success = pd.DataFrame(self.successful_jobs)
                    df_success.to_excel(writer, sheet_name='Successful', index=False)

                # Failed jobs sheet
                if self.failed_jobs:
                    df_failed = pd.DataFrame(self.failed_jobs)
                    df_failed.to_excel(writer, sheet_name='Failed', index=False)

                # Summary sheet
                self._add_comprehensive_summary(writer)

            logger.info(f"Bulk report generated: {self.output_file}")
            return self.output_file

        except Exception as e:
            logger.error(f"Error generating bulk report: {str(e)}")
            return None

    def _add_comprehensive_summary(self, writer):
        """Add comprehensive summary sheet"""
        try:
            summary_data = {
                'Metric': [
                    'Total Jobs Processed',
                    'Successfully Posted',
                    'Failed',
                    'Success Rate (%)',
                    'Generated At'
                ],
                'Value': [
                    len(self.successful_jobs) + len(self.failed_jobs),
                    len(self.successful_jobs),
                    len(self.failed_jobs),
                    f"{(len(self.successful_jobs) / (len(self.successful_jobs) + len(self.failed_jobs)) * 100):.1f}%" if (len(self.successful_jobs) + len(self.failed_jobs)) > 0 else "0%",
                    datetime.now().isoformat()
                ]
            }

            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

        except Exception as e:
            logger.warning(f"Could not add summary: {str(e)}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics"""
        total = len(self.successful_jobs) + len(self.failed_jobs)
        success_rate = (len(self.successful_jobs) / total * 100) if total > 0 else 0

        return {
            'total_jobs': total,
            'successful': len(self.successful_jobs),
            'failed': len(self.failed_jobs),
            'success_rate': f"{success_rate:.1f}%"
        }
