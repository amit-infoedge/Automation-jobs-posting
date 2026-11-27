"""
Main Automation Script for Job Posting
Entry point for the job posting automation workflow
"""

import logging
import sys
import pandas as pd
from typing import List, Dict, Optional, Any
from datetime import datetime
import traceback

from config import (
    TARGET_COMPANY_IDS, ACTION_SAVE, LOG_LEVEL, LOG_FILE,
    OUTPUT_DIR, API_RETRY_COUNT, COOKIE_API_ENDPOINT, COOKIE_API_USERNAME, COOKIE_API_PASSWORD,
    LOCATION_MAPPING_FILE, LOCATION_MAPPING_SHEET,
    INDUSTRY_FAREA_ROLE_FILE, INDUSTRY_SHEET
)
from database import DatabaseManager
from job_processor import JobProcessor, JobBuilder
from models import JobPostingRequest
from job_poster import JobPoster
from api_client import NaukriAPIClient
from job_validator_advanced import JobValidator
from sql_api_mapping import PayloadBuilder, SQLToAPIMapping
from error_reporter import BulkErrorReporter, JobPostingError
from authentication import CookieManager
import pandas as pd
import os

# Setup logging
def setup_logging():
    """
    Configure logging.

    The Windows console defaults to cp1252, which cannot encode the checkmarks
    and other non-ASCII characters in our log messages - that raises
    UnicodeEncodeError inside the handler and prints a traceback instead of the
    line. The file handler is forced to UTF-8, and the console is reconfigured
    to replace unencodable characters rather than blow up.
    """
    os.makedirs(os.path.dirname(LOG_FILE) if os.path.dirname(LOG_FILE) else '.', exist_ok=True)

    # Python 3.7+ can retarget the stream's codec in place.
    stream = sys.stdout
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            # Redirected to a pipe that will not take a new codec; the
            # errors="replace" wrapper below still keeps us safe.
            pass

    console_handler = logging.StreamHandler(stream)

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            console_handler
        ]
    )
    return logging.getLogger(__name__)


logger = setup_logging()


class PreflightError(Exception):
    """A required file or directory is missing, so the run must not start."""


def preflight_checks():
    """
    Verify everything the run depends on before a single job is posted.

    These used to fail soft: a missing mapping workbook logged a warning and
    left an empty DataFrame, so locations and industries silently went
    unmapped and jobs were posted incomplete; a missing output directory only
    surfaced after every job was live, when the results CSV could not be
    written. Both are unrecoverable once posting has started, so they are
    checked up front and abort the run.

    Raises:
        PreflightError: listing every problem found, not just the first
    """
    problems = []

    for label, path, sheet in (
        ("Location mapping", LOCATION_MAPPING_FILE, LOCATION_MAPPING_SHEET),
        ("Industry mapping", INDUSTRY_FAREA_ROLE_FILE, INDUSTRY_SHEET),
    ):
        if not os.path.isfile(path):
            problems.append(f"{label} file not found: {path}")
            continue
        try:
            df = pd.read_excel(path, sheet_name=sheet)
        except Exception as e:
            problems.append(f"{label} file unreadable ({path}, sheet '{sheet}'): {e}")
            continue
        if df.empty:
            problems.append(f"{label} sheet '{sheet}' is empty: {path}")

    # Created rather than merely checked - the log directory already works
    # this way, and an absent output directory is not a configuration error.
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        probe = os.path.join(OUTPUT_DIR, ".write_test")
        with open(probe, "w") as fh:
            fh.write("")
        os.remove(probe)
    except Exception as e:
        problems.append(f"Output directory not writable ({OUTPUT_DIR}): {e}")

    if problems:
        raise PreflightError(
            "Pre-flight checks failed - nothing was posted:\n  - "
            + "\n  - ".join(problems)
        )

    logger.info("[PREFLIGHT] All required files and directories are present")

# Naukri's own placeholder text - present when the account has never filled in a
# profile, so it must not be treated as one (Naukri.cs:1021).
COMPANY_PROFILE_PLACEHOLDER = "Enter details about your company"


def extract_hotjob_profile(ops_data: Dict[str, Any]) -> Optional[str]:
    """
    Pull companyDetail.hotjobProfile out of the operations response.

    This is the account-level company profile Naukri already holds; C# uses it
    whenever the sheet's own [Comp Prof] is missing or too short
    (Naukri.cs:1016-1018).

    Args:
        ops_data: Parsed operations response

    Returns:
        The profile text, or None when absent/placeholder/too short
    """
    if not isinstance(ops_data, dict):
        return None

    company_detail = ops_data.get('companyDetail')
    if not isinstance(company_detail, dict):
        return None

    profile = company_detail.get('hotjobProfile')
    if not profile:
        return None

    profile = str(profile).replace('\xa0', ' ').strip()

    if len(profile) < 10 or COMPANY_PROFILE_PLACEHOLDER in profile:
        logger.info("Account company profile is blank or still the Naukri placeholder")
        return None

    return profile


class JobPostingAutomation:
    """Main automation orchestrator"""

    def __init__(self, cookies: Dict[str, str], user_id: str, test_mode: bool = False):
        """
        Initialize automation

        Args:
            cookies: Authentication cookies
            user_id: Authenticated user ID
            test_mode: If True, skip make_live API calls
        """
        self.cookies = cookies
        self.user_id = user_id
        self.test_mode = test_mode
        self.db_manager = DatabaseManager()
        self.results = []

        # Mapping workbooks are mandatory: without them every location and
        # industry silently goes unmapped and jobs post incomplete, so a
        # failure here aborts rather than continuing with an empty frame.
        logger.info(f"Loading location mapping from {LOCATION_MAPPING_FILE}")
        self.location_mapping = pd.read_excel(LOCATION_MAPPING_FILE, sheet_name=LOCATION_MAPPING_SHEET)
        logger.info(f"✓ Loaded {len(self.location_mapping)} locations")

        logger.info(f"Loading industry mapping from {INDUSTRY_FAREA_ROLE_FILE}")
        self.industry_mapping = pd.read_excel(INDUSTRY_FAREA_ROLE_FILE, sheet_name=INDUSTRY_SHEET)
        logger.info(f"✓ Loaded {len(self.industry_mapping)} industries")

        # Junk phrases stripped from JDs, loaded once like RibbonController.cs:115
        self.junk_words = {}

        if test_mode:
            logger.info("="*80)
            logger.info("AUTOMATION RUNNING IN TEST MODE")
            logger.info("- Draft & Publish APIs will be called")
            logger.info("- Make Live API will be SKIPPED")
            logger.info("- Database updates will not be applied")
            logger.info("="*80)

    def fetch_jobs_from_db(self, company_ids: List[int], limit: int = None) -> pd.DataFrame:
        """
        Fetch jobs from database for processing

        Args:
            company_ids: List of company IDs
            limit: Optional LIMIT for testing (e.g., 1 for single job test)

        Returns:
            DataFrame with jobs to post
        """
        logger.info(f"Fetching jobs for companies: {company_ids}{f' with LIMIT {limit}' if limit else ''}")

        try:
            # Load junk phrases once, on the same open connection.
            if not self.junk_words:
                self.junk_words = self.db_manager.fetch_junk_words()

            df = self.db_manager.fetch_jobs_for_posting(company_ids, limit=limit)

            if df.empty:
                logger.warning("No jobs found for posting")
            else:
                logger.info(f"Fetched {len(df)} jobs for processing")

            return df

        except Exception as e:
            logger.error(f"Error fetching jobs: {str(e)}")
            return pd.DataFrame()

    def process_company_jobs(self, company_id: str, company_jobs: pd.DataFrame,
                            action: str = ACTION_SAVE) -> Dict[str, any]:
        """
        Process all jobs for a specific company

        Args:
            company_id: Company ID
            company_jobs: DataFrame with company's jobs
            action: Action type

        Returns:
            Dictionary with processing results
        """
        company_result = {
            'company_id': company_id,
            'total_jobs': len(company_jobs),
            'successful': 0,
            'failed': 0,
            'results': [],
            'errors': []
        }

        try:
            logger.info(f"Processing {len(company_jobs)} jobs for company {company_id}")

            # Initialize API client
            api_client = NaukriAPIClient(self.cookies)

            # The operations/resource calls are per company, so they take one
            # job type - use the first row's. Individual jobs still post under
            # their own [Posting Type].
            job_type = str(company_jobs.iloc[0].get('Posting Type') or 'h').strip().lower()
            if job_type not in ('c', 'h', 's'):
                job_type = 'h'

            distinct_types = {
                str(t).strip().lower()
                for t in company_jobs.get('Posting Type', pd.Series(dtype=object)).dropna()
            }
            if len(distinct_types) > 1:
                logger.warning(
                    f"Company {company_id} has mixed posting types {sorted(distinct_types)}; "
                    f"account lookups use '{job_type}'"
                )
            logger.info(f"Getting user ID for company {company_id}, job type: {job_type}")

            # Fetch user ID for this company using operations endpoint
            account_profile = None
            try:
                ops_data = api_client.get_operations(company_id, job_type)
                if ops_data and 'userId' in ops_data:
                    user_id = str(ops_data['userId'])
                    logger.info(f"✓ User ID fetched from operations API: {user_id}")
                else:
                    logger.error(f"No userId in operations response")
                    company_result['errors'].append("Could not get userId from operations API")
                    return company_result

                # The same response carries the account's company profile
                # (Naukri.cs:1016-1018 falls back to it when [Comp Prof] is short).
                account_profile = extract_hotjob_profile(ops_data)
                if account_profile:
                    logger.info(f"✓ Account company profile available ({len(account_profile)} chars)")
                else:
                    logger.warning("No companyDetail.hotjobProfile in the operations response")
            except Exception as e:
                logger.error(f"Failed to get user ID from operations API: {str(e)}")
                company_result['errors'].append(f"Failed to get user ID: {str(e)}")
                return company_result

            # Initialize job poster with location and industry mapping
            # self.user_id holds the login name ("customer_support"); user_id is the
            # numeric id from the operations API. add_email records the login name.
            poster = JobPoster(company_id, user_id, self.cookies, test_mode=self.test_mode, location_mapping=self.location_mapping, industry_mapping=self.industry_mapping, username=self.user_id, account_company_profile=account_profile, junk_words=self.junk_words)

            if not poster.initialize():
                logger.error(f"Failed to initialize poster for company {company_id}")
                company_result['errors'].append("Failed to initialize poster")
                return company_result

            logger.info(f"Poster initialized for company {company_id}")

            # Convert DataFrame rows to JobPostingRequest objects
            job_requests = []
            for idx, row in company_jobs.iterrows():
                try:
                    # The c/h/s posting type lives in [Posting Type]; the old
                    # 'Job_Type' key never matched, so every job was treated as
                    # h-type and the c-type branches never ran.
                    row_job_type = row.get('Posting Type')
                    row_job_type = str(row_job_type).strip().lower() if row_job_type else ''
                    if row_job_type not in ('c', 'h', 's'):
                        if row_job_type:
                            logger.warning(
                                f"Row {idx}: unexpected [Posting Type] "
                                f"{row_job_type!r}; defaulting to 'h'"
                            )
                        row_job_type = 'h'

                    request = JobPostingRequest(
                        row_data=row.to_dict(),
                        job_id=str(row.get('file', '')),
                        company_id=company_id,
                        job_type=row_job_type,
                        source=str(row.get('Source', 'offline'))
                    )
                    job_requests.append(request)
                except Exception as e:
                    logger.error(f"Error creating request for row {idx}: {str(e)}")
                    company_result['errors'].append(f"Row {idx}: {str(e)}")

            if not job_requests:
                logger.warning(f"No valid job requests created for company {company_id}")
                return company_result

            # Post jobs in bulk
            logger.info(f"Posting {len(job_requests)} jobs for company {company_id}")
            bulk_result = poster.post_jobs_bulk(job_requests, max_workers=5, action=action)

            # Update results
            company_result['successful'] = bulk_result.successful_jobs
            company_result['failed'] = bulk_result.failed_jobs
            company_result['results'] = bulk_result.results

            # Cleanup
            poster.cleanup()

            logger.info(f"Company {company_id} processing complete: {bulk_result.successful_jobs} successful, {bulk_result.failed_jobs} failed")

        except Exception as e:
            logger.error(f"Error processing company {company_id}: {str(e)}")
            logger.error(traceback.format_exc())
            company_result['errors'].append(str(e))

        return company_result

    def save_results(self, all_results: List[Dict]) -> str:
        """
        Save posting results to CSV files

        Args:
            all_results: List of company results

        Returns:
            Path to saved results file
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(OUTPUT_DIR, f"job_posting_results_{timestamp}.csv")

            all_records = []
            for company_result in all_results:
                for job_result in company_result.get('results', []):
                    record = {
                        'sr_no': job_result.job_sent_id,
                        'company_id': company_result['company_id'],
                        'title': job_result.posted_title,
                        'location': job_result.posted_location,
                        'success': job_result.success,
                        'job_id': job_result.new_job_id,
                        'made_live': job_result.made_live,
                        'db_updated': job_result.db_updated,
                        'db_status': job_result.db_status,
                        'message': job_result.message,
                        'errors': '; '.join(job_result.errors),
                        'original_job_id': job_result.original_job_id,
                        'duration_ms': job_result.posting_duration_ms,
                        'timestamp': job_result.posting_timestamp.isoformat() if job_result.posting_timestamp else None,
                    }
                    all_records.append(record)

            if all_records:
                results_df = pd.DataFrame(all_records)
                results_df.to_csv(output_file, index=False)
                logger.info(f"Results saved to {output_file}")
                return output_file
            else:
                logger.warning("No results to save")
                return None

        except Exception as e:
            logger.error(f"Error saving results: {str(e)}")
            return None

    def generate_summary(self, all_results: List[Dict]) -> Dict:
        """
        Generate summary of automation run

        Args:
            all_results: List of company results

        Returns:
            Summary dictionary
        """
        summary = {
            'total_companies': len(all_results),
            'total_jobs': sum(r['total_jobs'] for r in all_results),
            'successful_jobs': sum(r['successful'] for r in all_results),
            'failed_jobs': sum(r['failed'] for r in all_results),
            'companies': []
        }

        for company_result in all_results:
            summary['companies'].append({
                'company_id': company_result['company_id'],
                'jobs': company_result['total_jobs'],
                'successful': company_result['successful'],
                'failed': company_result['failed']
            })

        if summary['total_jobs'] > 0:
            summary['success_rate'] = (summary['successful_jobs'] / summary['total_jobs']) * 100
        else:
            summary['success_rate'] = 0

        return summary

    def run(self, company_ids: Optional[List[int]] = None, action: str = ACTION_SAVE, limit: int = None) -> bool:
        """
        Run the complete automation workflow

        Args:
            company_ids: Optional list of company IDs (uses config if not provided)
            action: Action type (SAVE, UPDATE, REFRESH, REPOST)
            limit: Optional LIMIT for testing (e.g., 1 for single job test)

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("=" * 80)
            logger.info("JOB POSTING AUTOMATION STARTED")
            logger.info(f"Mode: {'TEST' if self.test_mode else 'PRODUCTION'}")
            logger.info("=" * 80)

            if not company_ids:
                company_ids = TARGET_COMPANY_IDS

            logger.info(f"Target companies: {company_ids}")
            logger.info(f"Action: {action}")
            if limit:
                logger.info(f"Limit: {limit}")

            # Step 1: Fetch jobs from database
            logger.info("\n[STEP 1] Fetching jobs from database...")
            jobs_df = self.fetch_jobs_from_db(company_ids, limit=limit)

            if jobs_df.empty:
                logger.warning("No jobs found. Exiting.")
                return False

            # Step 2: Group jobs by company and job type
            logger.info("\n[STEP 2] Grouping jobs by company...")
            all_results = []

            for company_id in company_ids:
                company_jobs = jobs_df[jobs_df['Company id'] == company_id]

                if company_jobs.empty:
                    logger.info(f"No jobs for company {company_id}, skipping...")
                    continue

                # Process company jobs
                logger.info(f"\n[COMPANY {company_id}] Processing {len(company_jobs)} jobs...")
                company_result = self.process_company_jobs(
                    str(company_id),
                    company_jobs,
                    action=action
                )
                all_results.append(company_result)

            # Step 3: Save results
            logger.info("\n[STEP 3] Saving results...")
            results_file = self.save_results(all_results)

            # Step 4: Generate and display summary
            logger.info("\n[STEP 4] Generating summary...")
            summary = self.generate_summary(all_results)

            logger.info("\n" + "=" * 80)
            logger.info("AUTOMATION SUMMARY")
            logger.info("=" * 80)
            logger.info(f"Companies processed: {summary['total_companies']}")
            logger.info(f"Total jobs: {summary['total_jobs']}")
            logger.info(f"Successful: {summary['successful_jobs']}")
            logger.info(f"Failed: {summary['failed_jobs']}")
            logger.info(f"Success rate: {summary['success_rate']:.2f}%")
            logger.info(f"Results file: {results_file}")
            logger.info("=" * 80 + "\n")

            return summary['failed_jobs'] == 0

        except Exception as e:
            logger.error(f"Automation failed: {str(e)}")
            logger.error(traceback.format_exc())
            return False

        finally:
            try:
                self.db_manager.disconnect()
            except:
                pass


def main(test_mode: bool = False, limit: int = None):
    """
    Entry point

    Args:
        test_mode: If True, skip make_live API calls and DB updates
        limit: Optional LIMIT for testing (e.g., 1 for single job test)
    """
    try:
        logger.info("Starting Job Posting Automation")

        # Fail before any API or DB work if the run cannot complete correctly.
        try:
            preflight_checks()
        except PreflightError as e:
            logger.error(str(e))
            return False

        # Fetch cookies from API
        logger.info(f"[AUTH] Fetching authentication cookies from API...")
        cookie_manager = CookieManager(
            api_endpoint=COOKIE_API_ENDPOINT,
            username=COOKIE_API_USERNAME,
            password=COOKIE_API_PASSWORD
        )

        success, message = cookie_manager.fetch_cookies()
        if not success:
            logger.error(f"[AUTH] Failed to fetch cookies: {message}")
            return False

        cookies = cookie_manager.get_cookies()
        logger.info("[AUTH] ✓ Cookies fetched successfully")

        # Validate cookies
        is_valid, error = cookie_manager.validate_cookies()
        if not is_valid:
            logger.warning(f"[AUTH] Cookie validation warning: {error}")
            logger.info("[AUTH] Attempting to refresh cookies...")
            success, message = cookie_manager.refresh_cookies()
            if not success:
                logger.error(f"[AUTH] Failed to refresh cookies: {message}")
                return False
            logger.info("[AUTH] ✓ Cookies refreshed successfully")

        # Cookie status
        status = cookie_manager.get_cookie_status()
        logger.info(f"[AUTH] ✓ Cookie status: {len(status.get('cookie_keys', []))} cookies available")
        logger.info(f"[AUTH]   Valid: {status.get('is_valid')}")
        logger.info(f"[AUTH]   Last fetched: {status.get('last_fetched')}")

        # username used in cookie operations (matches postjob1.py)
        username = "customer_support"

        # Run automation
        automation = JobPostingAutomation(cookies, username, test_mode=test_mode)
        success = automation.run(
            company_ids=TARGET_COMPANY_IDS,
            action=ACTION_SAVE,
            limit=limit
        )

        return success

    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    test_mode = '--test' in sys.argv
    limit = None

    # Check for --limit argument
    if '--limit' in sys.argv:
        try:
            idx = sys.argv.index('--limit')
            limit = int(sys.argv[idx + 1])
        except (ValueError, IndexError):
            logger.warning("Invalid --limit argument, ignoring")

    if test_mode:
        logger.info("Running in TEST MODE (--test flag detected)")
    if limit:
        logger.info(f"Using LIMIT {limit} (--limit {limit} detected)")

    success = main(test_mode=test_mode, limit=limit)
    sys.exit(0 if success else 1)
