"""
Naukri API Client for Job Posting
"""

import json
import re
import requests
import logging
import time
from functools import wraps
from typing import Dict, List, Tuple, Optional, Any
from requests.exceptions import Timeout, RequestException, ConnectionError
from models import Job, CompanyDetails, SubUser
from config import (
    OPERATIONS_API, JOB_POSTING_API, PUBLISH_JOB_API, GET_JOB_API,
    COMPANY_DETAILS_API, SUB_USERS_API, DEFAULT_HEADERS,
    COMPANY_EMAILS_API, ADD_EMAIL_API,
    API_TIMEOUT, API_RETRY_COUNT, API_RETRY_DELAY
)

logger = logging.getLogger(__name__)


def retry_on_exception(max_retries=API_RETRY_COUNT, delay=API_RETRY_DELAY):
    """Decorator to retry API calls with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Timeout:
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)
                        logger.warning(f"[RETRY] Timeout on attempt {attempt + 1}/{max_retries}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"[ERROR] Max retries reached. API call failed due to timeout.")
                        raise
                except (ConnectionError, RequestException) as e:
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)
                        logger.warning(f"[RETRY] Request failed on attempt {attempt + 1}/{max_retries}: {str(e)[:100]}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"[ERROR] Max retries reached. API call failed: {str(e)[:100]}")
                        raise
                except Exception as e:
                    logger.error(f"[ERROR] Unexpected error in {func.__name__}: {str(e)[:200]}")
                    raise
            return None
        return wrapper
    return decorator


class NaukriAPIClient:
    """Client for Naukri Job Posting API"""

    def __init__(self, cookies: Dict[str, str], headers: Optional[Dict[str, str]] = None):
        """
        Initialize API client

        Args:
            cookies: Authentication cookies
            headers: Optional custom headers
        """
        self.cookies = cookies
        self.headers = headers or DEFAULT_HEADERS.copy()
        self.session = requests.Session()
        self.session.cookies.update(cookies)

    def _make_request(self, method: str, url: str, data: Optional[Dict] = None,
                     json_data: Optional[Dict] = None, allow_redirects: bool = False,
                     headers: Optional[Dict] = None) -> Tuple[int, str, Dict]:
        """
        Make HTTP request to API

        Args:
            method: HTTP method (GET, POST, etc.)
            url: API endpoint URL
            data: Form data
            json_data: JSON payload
            allow_redirects: Whether to follow redirects

        Returns:
            (status_code, response_text, response_headers)
        """
        try:
            kwargs = {
                'timeout': API_TIMEOUT,
                'allow_redirects': allow_redirects,
                'headers': headers if headers is not None else self.headers
            }

            if data:
                kwargs['data'] = data
            if json_data:
                kwargs['json'] = json_data

            if method.upper() == 'GET':
                response = self.session.get(url, **kwargs)
            elif method.upper() == 'POST':
                response = self.session.post(url, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            logger.info(f"[API] {method} {url} -> Status: {response.status_code}")
            return response.status_code, response.text, dict(response.headers)

        except Timeout:
            logger.error(f"[API] Request to {url} timed out after {API_TIMEOUT}s")
            raise
        except ConnectionError as e:
            logger.error(f"[API] Connection error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[API] Request error: {str(e)}")
            raise

    @retry_on_exception()
    def get_operations(self, company_id: str, category: str) -> Optional[Dict[str, Any]]:
        """
        Get job operations endpoint for creating new jobs and extracting userId

        Args:
            company_id: Company ID
            category: Job type ('s', 'h', 'c')

        Returns:
            Response JSON or None if failed
        """
        import re

        url = f"{OPERATIONS_API}?companyId={company_id}&category={category}"
        logger.info(f"[API] Getting operations for company {company_id}, category {category}")
        logger.debug(f"[API] URL: {url}")

        # Use allow_redirects=True to follow 302 redirects
        status, response_text, headers = self._make_request('GET', url, allow_redirects=True)

        if status != 200:
            logger.error(f"[API] Operations endpoint returned status {status}")
            logger.debug(f"Response text: {response_text[:200]}")
            return None

        payload = None

        # Newer responses are plain JSON.
        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError:
            # Older ones are HTML with the document in an `app = {...};`
            # variable (Naukri.cs:940).
            logger.debug("Could not parse as JSON, trying the embedded app variable...")
            app_match = re.search(r'app\s*=\s*(\{.+?\});\s*\n', response_text, re.DOTALL)
            if app_match:
                try:
                    payload = json.loads(app_match.group(1))
                    logger.info("[API] Parsed operations payload from the 'app' variable")
                except json.JSONDecodeError:
                    logger.debug("The 'app' variable was not valid JSON")

        if not isinstance(payload, dict):
            # Last resort: scrape just the userId (Naukri.cs method 3). Callers
            # lose companyDetail, but posting can still proceed.
            user_id_match = re.search(r'"userId"\s*:\s*(\d+)', response_text)
            if user_id_match:
                user_id = user_id_match.group(1)
                logger.info(f"[API] Extracted userId {user_id} by scraping the response")
                return {'userId': user_id}
            logger.error("Could not extract userId from operations response")
            logger.debug(f"Response text: {response_text[:500]}")
            return None

        # Normalise: C# reads the id at json["user"]["userId"] (Naukri.cs:1037),
        # so promote it to the top level for callers that expect it there.
        if 'userId' not in payload:
            nested = payload.get('user')
            if isinstance(nested, dict) and nested.get('userId') is not None:
                payload['userId'] = str(nested['userId'])
                logger.debug("[API] Promoted user.userId to the top level")
            else:
                scraped = re.search(r'"userId"\s*:\s*"?(\d+)"?', response_text)
                if scraped:
                    payload['userId'] = scraped.group(1)
                    logger.debug("[API] Recovered userId by scraping the response")
                else:
                    logger.error(
                        "Operations response has no userId "
                        f"(top-level keys: {sorted(payload.keys())[:12]})"
                    )

        return payload

    @retry_on_exception()
    def get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch existing job details

        Args:
            job_id: Job ID to fetch

        Returns:
            Job details JSON or None
        """
        url = f"{GET_JOB_API}/{job_id}"
        logger.info(f"[API] Fetching job details for {job_id}")

        status, response_text, _ = self._make_request('GET', url)

        if status == 200:
            try:
                job_data = json.loads(response_text)
                if job_data.get('statusCode') == 404:
                    logger.error(f"[API] Job {job_id} not found (404)")
                    return None
                return job_data
            except json.JSONDecodeError:
                logger.error("Failed to parse job details response")
                return None
        else:
            logger.error(f"[API] Failed to fetch job {job_id}: status {status}")
            return None

    @retry_on_exception()
    def save_job_draft(self, draft_data: Dict[str, Any], company_id: str = None, user_id: str = None, offline_user: str = "customer_support") -> Optional[str]:
        """
        Save job as draft

        Args:
            draft_data: Complete job draft data
            company_id: Company ID (for query parameters)
            user_id: User ID (for query parameters)
            offline_user: Offline user identifier (default: customer_support)

        Returns:
            Draft ID if successful, None otherwise
        """
        logger.info(f"[API] Saving job draft")
        logger.debug(f"[API] Draft payload: {json.dumps(draft_data, default=str)[:500]}...")

        # Build URL with query parameters for companyId, currentUser, and offlineUser
        url = JOB_POSTING_API
        if company_id and user_id:
            url = f"{JOB_POSTING_API}?companyId={company_id}&currentUser={user_id}&offlineUser={offline_user}"
            logger.debug(f"[API] URL with params: {url}")

        status, response_text, _ = self._make_request('POST', url, json_data=draft_data)

        if status == 200:
            try:
                response = json.loads(response_text)
                if response.get('_id'):
                    logger.info(f"[API] Draft saved with ID: {response['_id'][:12]}...")
                    return response['_id']
                else:
                    logger.error(f"[API] Draft save failed: {response.get('message', 'Unknown error')}")
                    logger.debug(f"[API] Full response: {response}")
                    return None
            except json.JSONDecodeError:
                logger.error("Failed to parse draft save response")
                logger.debug(f"Response text: {response_text[:500]}")
                return None
        else:
            logger.error(f"[API] Draft save returned status {status}")
            logger.debug(f"Response text: {response_text[:500]}")
            # Try to parse error message
            try:
                error_response = json.loads(response_text)
                logger.error(f"[API] Error message: {error_response.get('message', 'Unknown error')}")
            except:
                pass
            return None

    @retry_on_exception()
    def publish_job(self, publish_data: Dict[str, Any], company_id: str = None, user_id: str = None, offline_user: str = "customer_support") -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Publish job from draft

        Args:
            publish_data: Job data with draft ID
            company_id: Company ID (for query parameters)
            user_id: User ID (for query parameters)
            offline_user: Offline user identifier (default: customer_support)

        Returns:
            (success, job_id, error_message)
        """
        logger.info(f"[API] Publishing job")
        logger.debug(f"[API] Publish payload: {json.dumps(publish_data, default=str)[:500]}...")

        # Build URL with query parameters for companyId, currentUser, and offlineUser
        url = PUBLISH_JOB_API
        if company_id and user_id:
            url = f"{PUBLISH_JOB_API}?companyId={company_id}&currentUser={user_id}&offlineUser={offline_user}"
            logger.debug(f"[API] Publish URL with params: {url}")

        status, response_text, _ = self._make_request('POST', url, json_data=publish_data)

        if status == 200:
            try:
                response = json.loads(response_text)
                logger.debug(f"[API] Publish response: {json.dumps(response, default=str)}")

                redirect_url = response.get('redirectUrl')

                if redirect_url:
                    # Extract job ID from redirect URL
                    import re
                    match = re.search(r'(\d{12})', redirect_url)
                    if match:
                        job_id = match.group(1)
                        logger.info(f"[API] Job published successfully: {job_id}")
                        return True, job_id, None
                    else:
                        logger.error("Could not extract job ID from redirect URL")
                        logger.error(f"Redirect URL: {redirect_url}")
                        return False, None, "Invalid redirect URL"
                else:
                    # Check for error in response
                    error_msg = response.get('message') or response.get('error') or response.get('err') or 'Unknown error'

                    # Check if there's a boards object with error info
                    if 'boards' in response:
                        boards = response.get('boards', {})
                        if isinstance(boards, dict):
                            for board_id, board_data in boards.items():
                                if isinstance(board_data, dict) and 'posting' in board_data:
                                    posting = board_data.get('posting', {})
                                    if isinstance(posting, dict) and 'err' in posting:
                                        error_msg = posting.get('err')
                                        logger.error(f"[API] Board {board_id} error: {error_msg}")

                    logger.error(f"[API] Job publish failed: {error_msg}")
                    logger.debug(f"[API] Full response: {response}")
                    return False, None, error_msg
            except json.JSONDecodeError:
                logger.error("Failed to parse publish response")
                logger.debug(f"Response text: {response_text[:500]}")
                return False, None, "Invalid response format"
        else:
            logger.error(f"[API] Publish returned status {status}")
            logger.debug(f"Response text: {response_text[:500]}")
            # Try to parse error message
            try:
                error_response = json.loads(response_text)
                logger.error(f"[API] Error message: {error_response.get('message', 'Unknown error')}")
            except:
                pass
            return False, None, f"HTTP {status}"

    @retry_on_exception()
    def get_job_resource(self, company_id: str, user_id: str, job_type: str, subscription_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Fetch the company resource document (ORE.cs GetJobResource, line 1150).

        Carries more than the company name - addressList feeds
        companyDetail.address and companyDetail.consultant decides the
        registrationType - so the whole document is returned.

        Args:
            company_id: Company ID
            user_id: User ID
            job_type: Job type
            subscription_id: Optional subscription ID

        Returns:
            Parsed resource document, or None
        """
        subs_param = f"&subscriptionId={subscription_id}" if subscription_id else ""
        # Note: jobType parameter uses ?jobType= format (with = sign)
        url = f"{COMPANY_DETAILS_API}/{company_id}/recruiters/{user_id}/all?jobType={job_type}{subs_param}"

        logger.info(f"[API] Fetching company resource for {company_id}, user_id: {user_id}, job_type: {job_type}")
        logger.debug(f"[API] URL: {url}")

        status, response_text, _ = self._make_request('GET', url)

        if status != 200:
            logger.error(f"[API] Failed to get company resource: status {status}")
            logger.debug(f"Response text: {response_text[:200]}")
            return None

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            logger.error("Failed to parse company resource response")
            logger.debug(f"Response text: {response_text[:200]}")
            return None

        if not isinstance(data, dict):
            logger.error("Company resource response was not a JSON object")
            return None

        return data

    def get_company_details(self, company_id: str, user_id: str, job_type: str, subscription_id: Optional[str] = None) -> Optional[str]:
        """
        Get the company name.

        Thin wrapper over get_job_resource, kept for callers that only need the
        name.

        Returns:
            Company name or None
        """
        data = self.get_job_resource(company_id, user_id, job_type, subscription_id)
        if data is None:
            return None

        company_name = data.get('groupDetails', {}).get('linkedCompanyName', '')
        logger.info(f"[API] Company name: {company_name}")
        return company_name

    @retry_on_exception()
    def get_sub_users(self, company_id: str) -> Optional[List[SubUser]]:
        """
        Get sub-users for a company

        Args:
            company_id: Company ID

        Returns:
            List of SubUser objects or None
        """
        url = f"{SUB_USERS_API}/{company_id}?currentUser=1"
        logger.info(f"[API] Fetching sub-users for company {company_id}")

        status, response_text, _ = self._make_request('POST', url, json_data={})

        if status == 200:
            try:
                data = json.loads(response_text)
                sub_users = []

                # Process sub-users
                if 'subUsers' in data:
                    for user_id, user_data in data['subUsers'].items():
                        sub_users.append(SubUser(
                            user_id=int(user_id),
                            name=user_data.get('name', ''),
                            email=user_data.get('actualEmail', ''),
                            is_active=user_data.get('active', True)
                        ))

                # Add super user
                if 'superUser' in data:
                    super_user = data['superUser']
                    sub_users.append(SubUser(
                        user_id=int(super_user.get('userId', 0)),
                        name=super_user.get('name', ''),
                        email=super_user.get('actualEmail', ''),
                        is_super_user=True,
                        is_active=True
                    ))

                logger.info(f"[API] Found {len(sub_users)} sub-users")
                return sub_users
            except json.JSONDecodeError:
                logger.error("Failed to parse sub-users response")
                return None
        else:
            logger.error(f"[API] Failed to get sub-users: status {status}")
            return None

    @retry_on_exception()
    def get_registered_emails(self, company_id: str, posting_type: str = 'h') -> List[str]:
        """
        Get the auto-forward emails already registered for a company.

        Mirrors ORE.cs GetEmail (line 282-335) which GETs
        /companies/{company_id}/emails?jobType=h and returns the email column.

        Args:
            company_id: Company ID
            posting_type: Posting type (C# always sends jobType=h regardless)

        Returns:
            List of lowercase registered email addresses (empty list on failure)
        """
        url = f"{COMPANY_EMAILS_API}/{company_id}/emails?jobType=h"
        logger.info(f"[API] Fetching registered emails for company {company_id}")

        status, response_text, _ = self._make_request('GET', url)

        if status != 200:
            logger.error(f"[API] Failed to get registered emails: status {status}")
            return []

        try:
            data = json.loads(response_text)
            emails = []
            for entry in data or []:
                email = (entry or {}).get('email')
                if email:
                    emails.append(str(email).strip().lower())
            logger.info(f"[API] Found {len(emails)} registered emails")
            return emails
        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            logger.error(f"[API] Failed to parse registered emails: {str(e)}")
            return []

    @retry_on_exception()
    def add_email(self, company_id: str, email: str, username: str) -> bool:
        """
        Register a new auto-forward email for a company.

        Mirrors ORE.cs AddEmail (line 261-270) which POSTs
        {"email": <lowercase>, "addedBy": <username>} to /email/{company_id}/h

        Args:
            company_id: Company ID
            email: Email address to register
            username: Login name recorded as addedBy

        Returns:
            True if the email was registered
        """
        url = f"{ADD_EMAIL_API}/{company_id}/h"
        payload = {'email': str(email).strip().lower(), 'addedBy': username}
        logger.info(f"[API] Registering auto-forward email {payload['email']} for company {company_id}")

        status, response_text, _ = self._make_request('POST', url, json_data=payload)

        if status == 200:
            logger.info(f"[API] Email registered: {payload['email']}")
            return True

        logger.error(f"[API] Failed to register email {payload['email']}: status {status}, body {response_text}")
        return False

    @retry_on_exception()
    def refresh_jobs(self, company_id: str, user_id: str, job_ids: List[str]) -> Dict[str, bool]:
        """
        Refresh multiple jobs

        Args:
            company_id: Company ID
            user_id: User ID
            job_ids: List of job IDs to refresh

        Returns:
            Dictionary mapping job_id to success status
        """
        url = f"{NAUKRI_BASE_URL}/cloudgateway-jobposting/job-services/v1/job/offline/live/refresh"
        url += f"?companyId={company_id}&currentUser={user_id}&offlineUser=automation"

        payload = {"jobIds": job_ids, "decrementJobCounter": True}
        logger.info(f"[API] Refreshing {len(job_ids)} jobs")

        status, response_text, _ = self._make_request('POST', url, json_data=payload)

        if status == 200:
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                logger.error("Failed to parse refresh response")
                return {}
        else:
            logger.error(f"[API] Refresh failed: status {status}")
            return {}

    @retry_on_exception()
    def make_live(self, job_id: str, company_id: str, current_user: str,
                  offline_user: str) -> Tuple[bool, Optional[str]]:
        """
        Make a posted job live.

        Mirrors ORE.cs:1159 - the JSON gateway endpoint the current posting flow
        uses. The legacy Offline.php/Single/makeLive form endpoint is dead for
        this account (it needs a SUMSID session cookie that the new auth no
        longer issues) and returns 404.

        Args:
            job_id: Job ID, or a comma-separated list of them
            company_id: Company ID
            current_user: Numeric user id from the operations API
            offline_user: Offline login name

        Returns:
            (success, response_text_or_error)
        """
        url = (
            f"{NAUKRI_BASE_URL}/cloudgateway-jobposting/job-services/v1/job/offline/live"
            f"?companyId={company_id}&currentUser={current_user}&offlineUser={offline_user}"
        )
        payload = {'jobIds': [j.strip() for j in str(job_id).split(',') if j.strip()]}

        logger.info(f"[API] Making job {job_id} live")

        try:
            status, response_text, _ = self._make_request('POST', url, json_data=payload)

            if status != 200:
                logger.error(
                    f"[API] Make live failed for job {job_id}: status {status}\n"
                    f"  URL: {url}\n"
                    f"  Payload: {json.dumps(payload)}\n"
                    f"  Response body (first 1000 chars): {response_text[:1000]}"
                )
                return False, f"HTTP {status}"

            # ORE.cs treats the call as done only when the job comes back under
            # `success` - a 200 with the id under a failure bucket is not live.
            response = json.loads(response_text)
            succeeded = response.get('success') or []

            if len(succeeded) == len(payload['jobIds']):
                logger.info(f"[API] Job {job_id} made live successfully")
                return True, response_text

            logger.error(
                f"[API] Make live did not confirm job {job_id}: "
                f"{len(succeeded)}/{len(payload['jobIds'])} in 'success'\n"
                f"  Response body (first 1000 chars): {response_text[:1000]}"
            )
            return False, f"Not confirmed live: {response_text[:200]}"

        except json.JSONDecodeError:
            logger.error(
                f"[API] Make live returned non-JSON for job {job_id}: "
                f"{response_text[:500]}"
            )
            return False, "Invalid JSON response"
        except Exception as e:
            logger.error(f"[API] Make live exception: {str(e)}", exc_info=True)
            return False, str(e)

    def close(self):
        """Close session"""
        if self.session:
            self.session.close()
            logger.info("API client session closed")


# Import at the end to avoid circular imports
from config import NAUKRI_BASE_URL
