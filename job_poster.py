"""
Main Job Posting Orchestrator
Coordinates the complete job posting workflow
"""

import logging
import json
import html
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

from models import (
    Job, JobPostingRequest, JobPostingResult, BulkPostingResult,
    CompanyDetails, SubUser
)
from api_client import NaukriAPIClient, retry_on_exception
from database import DatabaseManager
from job_processor import JobProcessor, JobBuilder, JobValidator
from job_validator_advanced import TitleValidator
from config import ACTION_SAVE, ACTION_UPDATE, API_TIMEOUT
from typing import Tuple

logger = logging.getLogger(__name__)

# Companies that restrict assigned sub-users to one named recruiter plus the
# super user, and force ResponseMode to rms - Naukri.cs lines 1044-1063.
# These are also the accounts whose company address is blanked out (ORE.cs:561).
INTERNAL_COMPANY_SUBUSERS = {
    "678662": "premiumjobs@naukri.comm",
    "852658": "qualityjobs@naukri.com",
    "872138": "kanika.malhotra@naukri.comm",
    "5145492": "palak.goyal@naukri.comm",
}

# Matches the email validation regex in Naukri.cs:1141
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,8}$')


# Value C# sends on the publish request (ORE.cs:1082). Kept identical so the
# backend sees the same platform string it already accepts from the Excel client.
SOURCE_PLATFORM = "offline_excel"

# Written to a row whose job title fails validation, instead of posting it.
INVALID_TITLE_STATUS = "Pending"
INVALID_TITLE_COMMENT = "Appropriate Position title not given"


class JobPostingValidationError(Exception):
    """A pre-flight check failed, so the job must not be posted at all."""


class JobPoster:
    """Main job posting orchestrator"""

    def __init__(self, company_id: str, user_id: str, cookies: Dict[str, str], test_mode: bool = False, location_mapping=None, industry_mapping=None, username: str = "customer_support", account_company_profile: Optional[str] = None, junk_words: Optional[Dict[str, List[str]]] = None):
        """
        Initialize JobPoster

        Args:
            company_id: Company ID
            user_id: User ID
            cookies: Authentication cookies
            test_mode: If True, skip make_live API call
            location_mapping: DataFrame with location ID to name mapping
            industry_mapping: DataFrame with industry label to ID mapping
            username: Login name recorded as addedBy when registering emails
            account_company_profile: companyDetail.hotjobProfile from the
                operations response, used when the row has no [Comp Prof]
            junk_words: {company_id: [phrase, ...]} stripped from JDs
        """
        self.company_id = company_id
        self.user_id = user_id
        self.cookies = cookies
        self.test_mode = test_mode
        self.username = username
        self.account_company_profile = account_company_profile
        self.api_client = NaukriAPIClient(cookies)
        self.db_manager = DatabaseManager()
        self.processor = JobProcessor(location_mapping_df=location_mapping, industry_mapping_df=industry_mapping, junk_words=junk_words)
        self.job_builder = JobBuilder(self.processor)
        self.company_details = None
        self.sub_users = []
        # Filled by initialize() from the company resource document.
        self.company_address = "."
        self.company_type = ""

        if test_mode:
            logger.info("JobPoster initialized in TEST MODE - make_live API will be skipped")

    def initialize(self) -> bool:
        """
        Initialize poster with company details and sub-users

        Returns:
            True if initialization successful
        """
        try:
            logger.info(f"Initializing JobPoster for company {self.company_id}")

            # One call gives the name, the address and the consultant flag
            # (ORE.cs:468-479 does the same with GetJobResource).
            resource = self.api_client.get_job_resource(
                self.company_id, self.user_id, 'h'
            )

            if not resource:
                logger.error("Failed to fetch company resource")
                return False

            company_name = resource.get('groupDetails', {}).get('linkedCompanyName', '')
            if not company_name:
                logger.error("Failed to fetch company details")
                return False

            self.company_address = self._build_company_address(resource)
            self.company_type = str(
                (resource.get('companyDetail') or {}).get('consultant', '')
            ).strip()
            logger.info(
                f"Company address: {self.company_address!r} | consultant: {self.company_type!r}"
            )

            # Get sub-users
            sub_users = self.api_client.get_sub_users(self.company_id)
            if sub_users is None:
                logger.error("Failed to fetch sub-users")
                return False

            self.company_details = CompanyDetails(
                company_id=self.company_id,
                company_name=company_name or "",
                user_id=self.user_id,
                sub_users=sub_users or []
            )
            self.sub_users = sub_users or []

            logger.info(f"JobPoster initialized: {company_name} ({len(self.sub_users)} users)")
            return True

        except Exception as e:
            logger.error(f"Initialization failed: {str(e)}")
            return False

    def resolve_response_mode(self, job: Job) -> str:
        """
        Resolve the effective response mode for a job.

        [Responses] is the only input. Internal companies also set rms in
        Naukri.cs:1044-1063, but the [Responses] chain that follows it ends in an
        unconditional else, so that assignment is always overwritten - the
        company block's only lasting effect is the named sub-user.

        Returns:
            'rms', 'companyUrl', or 'ATS'
        """
        mode = job.response_mode or self.processor.resolve_response_mode(job.responses)
        logger.info(f"Response mode for job '{job.position}': {mode} (Responses='{job.responses}')")
        return mode

    def resolve_auto_forward_emails(self, job: Job) -> List[str]:
        """
        Build the auto-forward email list from [Responses].

        Mirrors Naukri.cs lines 1133-1158: the emails live inside [Responses]
        itself, semicolon-separated. Each one is checked against the company's
        already-registered emails and registered on the fly when missing.
        Invalid addresses are skipped and reported.

        Returns:
            List of registered email addresses (may be empty)
        """
        responses = str(job.responses or "")
        if "@" not in responses:
            return []

        registered = set(self.api_client.get_registered_emails(self.company_id, job.job_type) or [])
        auto_forward = []

        for candidate in responses.split(';'):
            candidate = candidate.strip().lower()
            if not candidate:
                continue

            if candidate in registered:
                auto_forward.append(candidate)
                continue

            if not EMAIL_PATTERN.match(candidate):
                logger.warning(f"'{candidate}' is not a valid email - skipping")
                continue

            # New address: register it with the company before using it.
            if self.api_client.add_email(self.company_id, candidate, self.username):
                logger.info(f"Registered new auto-forward email: {candidate}")
            else:
                logger.warning(f"Could not register {candidate}; sending it anyway")
            auto_forward.append(candidate)

        logger.info(f"Auto-forward emails resolved: {auto_forward}")
        return auto_forward

    def resolve_assigned_sub_users(self, response_mode: str) -> List[int]:
        """
        Build the assignedSubUsers list.

        Mirrors Naukri.cs lines 1104-1130: sub-users are assigned ONLY when the
        response mode is 'rms'. For internal companies the list is narrowed to
        the one named recruiter plus the super user; every other company gets
        all sub-users plus the super user.

        Returns:
            List of user IDs (empty when mode is not 'rms')

        Raises:
            JobPostingValidationError: internal company whose named recruiter is
                not in the sub-user list - C# aborts the post here.
        """
        if response_mode != "rms":
            logger.info(f"Response mode is '{response_mode}' - no sub-users assigned")
            return []

        named_recruiter = INTERNAL_COMPANY_SUBUSERS.get(str(self.company_id))

        if named_recruiter:
            target = named_recruiter.lower().replace("\n", "")
            selected = [
                u for u in self.sub_users
                if (u.email or "").lower() == target or u.is_super_user
            ]
            if not selected:
                # Naukri.cs:1121-1125 returns this error and stops posting.
                raise JobPostingValidationError(
                    "UserName not found in Manager User Section."
                )
        else:
            selected = list(self.sub_users)

        user_ids = [u.user_id for u in selected if u.user_id]
        logger.info(f"Assigned {len(user_ids)} sub-users for response mode 'rms'")
        return user_ids

    def build_response_manager(self, job: Job) -> Tuple[str, Dict[str, Any]]:
        """
        Build the responseManager type and responseManagerSettings payload.

        Mirrors ORE.cs lines 597-620:
          - rms with emails -> emails + frequency + subjectSettings + relevanceRating
          - rms without emails -> empty settings object
          - companyUrl -> only companyUrl
          - ATS -> empty settings object

        Returns:
            (response_manager_type, response_manager_settings)
        """
        response_mode = self.resolve_response_mode(job)

        if response_mode == "companyUrl":
            company_url = str(job.response_url or "").strip()
            if not company_url:
                logger.warning(
                    f"Job '{job.position}' is a companyUrl job but [URL] is empty"
                )
            return "companyUrl", {'companyUrl': company_url}

        if response_mode == "rms":
            emails = self.resolve_auto_forward_emails(job)
            if not emails:
                # C# leaves responseManagerSettings empty when there is no email.
                return "rms", {}

            # frequency: premium always gets the digest, otherwise EmailResponse
            # decides, with anything falsy/'N' meaning per-apply (ORE.cs:605-613).
            process = str(job.process or "").lower()
            if process == "premium":
                frequency = "Daily summary"
            else:
                email_response = str(job.email_response or "").strip().upper()
                frequency = "On every new apply" if email_response in ("", "N") else "Daily summary"

            return "rms", {
                'emails': emails,
                'frequency': frequency,
                'subjectSettings': {
                    'Company': True,
                    'Designation': True,
                    'Experience': True,
                    'isSubjectCustomized': False,
                    'Location': True
                },
                'relevanceRating': self.processor.calculate_rating(job.paf_str)
            }

        # ATS and anything unexpected: type only, no settings.
        return response_mode, {}

    def _build_company_address(self, resource: Dict[str, Any]) -> str:
        """
        Build companyDetail.address from the resource document.

        Based on ORE.cs:555-562, with one deliberate difference: C# only formats
        an address when addressList.Count > 1 (then still reads [0]), so an
        account with exactly one address on file gets ".". That drops a
        perfectly good address, so here a single entry is used. "." is reserved
        for genuinely having no address - empty list, or a blank primaryAddress.

        Internal accounts are always blanked to "." regardless (ORE.cs:561).

        Args:
            resource: Parsed company resource document

        Returns:
            The formatted address, or "."
        """
        # Internal accounts never publish an address (ORE.cs:561).
        if str(self.company_id) in INTERNAL_COMPANY_SUBUSERS:
            logger.info(f"Company {self.company_id} is internal - address blanked")
            return "."

        address_list = resource.get('addressList')
        if not isinstance(address_list, list) or not address_list:
            return "."

        first = address_list[0]
        if not isinstance(first, dict):
            return "."

        # No street line means there is no usable address to publish.
        primary = str(first.get('primaryAddress') or "").strip()
        if not primary:
            return "."

        parts = [
            primary,
            first.get('city'),
            first.get('state'),
            first.get('country'),
        ]
        # Drop empty trailing fields rather than emitting ", , ".
        return ", ".join(
            str(p).strip() for p in parts if p is not None and str(p).strip()
        )

    @staticmethod
    def _is_title_rejection(error_msg: Any) -> bool:
        """
        Decide whether a publish error is the API rejecting the job title.

        The response names the offending field, e.g.
        {"validationErrors":[{"field":"title","customErrorCode":400007,
        "message":"Job title cannot have more than 5 numbers"}]}
        so the field marker is matched rather than the wording, which varies
        per rule and can change server-side.
        """
        if not error_msg:
            return False

        text = str(error_msg).lower()
        return '"field":"title"' in text.replace(' ', '') or 'job title' in text

    @staticmethod
    def _title_error_comment(error_msg: Any) -> str:
        """
        Reduce a publish error to the human-readable reason for the DB comment.

        The raw payload is JSON, which is unreadable in [Job_Listing Comments],
        so pull out the validation message when one is present.
        """
        text = str(error_msg or "").strip()

        try:
            data = json.loads(text)
            for err in data.get('validationErrors') or []:
                message = str(err.get('message') or "").strip()
                if message:
                    return message[:250]
            top = str(data.get('message') or "").strip()
            if top:
                return top[:250]
        except (ValueError, AttributeError):
            pass

        return text[:250] or INVALID_TITLE_COMMENT

    def _mark_invalid_title(self, job: Job, title_status: str,
                            comment: str = INVALID_TITLE_COMMENT,
                            result: Optional[JobPostingResult] = None) -> None:
        """
        Flag a job whose title was rejected so it is picked up for review.

        Covers both the local title gate and a title rejected by the publish API
        (400007 and friends) - either way the row needs a human to fix the title,
        so it goes back to Pending rather than staying unmarked and re-posting.

        Writes [Job_Listing Status] = 'Pending' and the comment. Skipped in test
        mode - test runs must not touch the source rows.

        Args:
            result: when given, records whether the write landed so the results
                CSV can tell "marked Pending" apart from "nothing written"
        """
        if self.test_mode:
            logger.info(
                f"[TEST MODE] Not flagging '{job.position}' in the DB "
                f"(would set Pending / '{comment}')"
            )
            return

        if not job.job_sent_id:
            logger.error(
                f"Cannot flag '{job.position}' as Pending: row has no [Sr No]"
            )
            return

        written = bool(self.db_manager.update_listing_status_by_sr_no(
            job.job_sent_id, INVALID_TITLE_STATUS, comment
        ))

        if result is not None:
            result.db_updated = written
            if written:
                result.db_status = INVALID_TITLE_STATUS

    @staticmethod
    def build_all_info(request: JobPostingRequest, title: str, location: str) -> str:
        """
        Build the [All_Info] snapshot written back after a successful post.

        Layout (the '%' separator is what the downstream readers split on):
        cid%cname%title%location%exp%ctc%industry%farea%role%keywords%ug%pg
        then title and location again, unseparated, matching the legacy format.
        """
        sep = "%"
        parts = [
            str(request.company_id or ""),
            str(request.extract_field('Company Name', '') or ""),
            title,
            location,
            str(request.extract_field('Exp', '') or ""),
            str(request.extract_field('CTC', '') or ""),
            str(request.extract_field('Industry', '') or ""),
            str(request.extract_field('Functional Area', '') or ""),
            str(request.extract_field('Role', '') or ""),
            str(request.extract_field('Keyword', '') or ""),
            str(request.extract_field('UG', '') or ""),
            str(request.extract_field('PG', '') or ""),
        ]
        return sep.join(parts) + title + location

    def _mark_job_posted(self, result: JobPostingResult) -> None:
        """
        Write a successful post back to its source row.

        Skipped in test mode - test runs must not touch the source rows, same as
        _mark_invalid_title.
        """
        if self.test_mode:
            logger.info(
                f"[TEST MODE] Not updating [Sr No]={result.job_sent_id} in the DB "
                f"(would set Posted / [Job Id]={result.new_job_id})"
            )
            return

        if not result.job_sent_id:
            logger.error(
                f"Cannot mark job {result.new_job_id} Posted: row has no [Sr No]"
            )
            return

        result.db_updated = bool(self.db_manager.mark_job_posted(
            result.job_sent_id,
            result.new_job_id,
            result.posted_title,
            result.posted_location,
            result.all_info,
        ))
        if result.db_updated:
            result.db_status = "Posted"

        if not result.db_updated:
            # Live on Naukri but unmarked - it will be re-fetched and posted
            # again unless someone reconciles it.
            logger.error(
                f"[Sr No: {result.job_sent_id}] Job {result.new_job_id} is LIVE "
                f"but the DB write FAILED - needs reconciling before the next run"
            )

    def build_applied_filters(self, job: Job, national_locations_gid: Dict[str, Any],
                              international_locations_gid: Dict[str, Any],
                              ug_gid: List[Any], pg_gid: List[Any], ppg_gid: List[Any],
                              degree_combination: str) -> Dict[str, Any]:
        """
        Build the appliedFilters (PAF) object.

        Mirrors ORE.cs lines 792-920. The skeleton with all five filters null and
        relevanceRating "medium" is ALWAYS sent; individual filters are only
        populated when [PAF] mentions them. A [CandidateIndustry] value implicitly
        appends "ind" to the PAF string (ORE.cs:802-807), and the whole block is
        gated on the PAF string being longer than 2 characters (ORE.cs:808).

        Returns:
            The appliedFilters payload
        """
        paf = {
            'experience': None,
            'location': None,
            'salary': None,
            'industry': None,
            'education': None,
            'relevanceRating': "medium",
        }

        paf_str = str(job.paf_str or "")
        candidate_industry = str(job.candidate_industry or "")

        # A candidate industry implicitly turns on the industry filter.
        if len(candidate_industry) > 2:
            paf_str = paf_str + "ind"

        # PremiumChk is not in the current SELECT, so only the length gate applies.
        if len(paf_str) <= 2:
            return paf

        paf_str = paf_str.lower()
        logger.info(f"Building appliedFilters from PAF='{paf_str}'")

        if "exp" in paf_str:
            # An explicit "exp 5-10" in the PAF overrides the job's own range.
            match = re.search(r'exp.*?(\d+)-(\d+)', paf_str, re.IGNORECASE | re.DOTALL)
            if match:
                min_exp, max_exp = self.processor.parse_experience(
                    f"{match.group(1)}-{match.group(2)}"
                )
            else:
                min_exp, max_exp = job.min_experience, job.max_experience
            paf['experience'] = {
                'minimumExperience': str(min_exp),
                'maximumExperience': str(max_exp),
            }

        # C# also enables this via the `relocate` flag, which has no DB column here.
        if "loc" in paf_str:
            paf['location'] = {
                'nationalLocations': national_locations_gid,
                'internationalLocations': international_locations_gid,
                'otherNationalLocations': job.other_national_locations or [],
                'otherInternationalLocations': job.other_international_locations or [],
                'willingToRelocateFlag': True,
            }

        if "ind" in paf_str:
            # Prefer the candidate industry, else fall back to the job's industry.
            source = candidate_industry if len(candidate_industry) > 2 else str(job.industry_gid or "")
            industry_gids = [g.strip() for g in source.split('-')[0].strip().split(',') if g.strip()]
            paf['industry'] = {
                'industryGIds': industry_gids,
                'industryOtherLabels': None,
                'industryOtherFlag': True,
            }

        if "sal" in paf_str or "ctc" in paf_str:
            match = re.search(r'ctc.*?(\d+)-(\d+)', paf_str, re.IGNORECASE | re.DOTALL)
            if match:
                min_ctc, max_ctc, _ = self.processor.parse_salary(
                    f"{match.group(1)}-{match.group(2)}"
                )
            elif job.salary_detail:
                min_ctc = job.salary_detail.minimum_salary
                max_ctc = job.salary_detail.maximum_salary
            else:
                min_ctc, max_ctc = 0, 0
            paf['salary'] = {
                'maximumSalary': str(int(max_ctc)),
                'minimumSalary': str(int(min_ctc)),
                'salaryCurrency': "INR",
                'salaryZeroFlag': True,
            }

        # C# also enables this via PremiumChk, which has no DB column here.
        if "edu" in paf_str:
            # C# sends null rather than an empty array for a missing level.
            paf['education'] = {
                'anyEducationFlag': False,
                'ugEducationGId': ug_gid or None,
                'pgEducationGId': pg_gid or None,
                'ppgEducationGId': ppg_gid or None,
                'degreeCombination': degree_combination,
            }

        return paf

    def prepare_job_payload(self, job: Job, action: str = ACTION_SAVE, company_type: str = "company") -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Prepare complete job payload for API (both draft save and publish)

        Matches ORE.cs PostJob() method lines 665-1028 exactly

        Args:
            job: Job object
            action: Action type (SAVE, UPDATE, etc.)
            company_type: "company" or "consultant" - affects registrationType

        Returns:
            Tuple of (draft_payload, publish_payload)
        """
        try:
            # Build location objects - ORE.cs lines 754-787
            national_locations_gid = {}
            location_count = 0
            for loc in job.national_locations:
                national_locations_gid[loc.location_id] = {
                    'id': loc.location_id,
                    'label': loc.location_name
                }
                location_count += 1

            international_locations_gid = {}
            for loc in job.international_locations:
                international_locations_gid[loc.location_id] = {
                    'id': loc.location_id,
                    'label': loc.location_name
                }

            # baseLocation only set if wfh=="2" AND locationCount<2 - ORE.cs lines 932-941
            base_location = None
            if hasattr(job, 'wfh') and job.wfh == "2" and location_count < 2:
                base_location = {
                    'nationalLocations': national_locations_gid,
                    'internationalLocations': international_locations_gid,
                    'otherNationalLocations': job.other_national_locations or [],
                    'otherInternationalLocations': job.other_international_locations or []
                }

            # Key Skills - ORE.cs lines 712-733
            # Every keyword goes in with preferred="false", then each mandatory
            # keyword is written over the top with preferred="true". C# assigns by
            # key, so a mandatory keyword absent from [Keywords] is ADDED, and the
            # flag is the STRING "true"/"false", not a JSON boolean.
            key_skills_gid = {}
            for skill_name in (job.key_skills or {}):
                label = str(skill_name).strip()
                if label:
                    key_skills_gid[label] = {'label': label, 'preferred': "false"}

            for keyword in (job.mandatory_keywords or []):
                label = str(keyword).strip()
                if label:
                    key_skills_gid[label] = {'label': label, 'preferred': "true"}

            # Company Detail - ORE.cs lines 645-663, 690, 693, 1025
            # Clean whitespace but preserve HTML tags
            def clean_html_content(text):
                """
                Clean text for HTML field - replace problematic whitespace
                Matches ORE.cs lines 690, 693, 1025: Replace char(160) = non-breaking space
                """
                if not text:
                    return ""
                text = str(text)
                # Replace non-breaking space (char 160 = \xa0) with regular space
                # This is what C# does: Convert.ToChar(160).ToString() = '\xa0'
                text = text.replace('\xa0', ' ')
                # Also handle other problematic whitespace
                text = text.replace(' ', ' ')  # Unicode non-breaking space
                return text

            def clean_jd(text):
                """
                Clean JD per C# Data.CleanJD logic (Data.cs:171-234)
                Keeps ALLOWED HTML tags, removes disallowed ones
                NOT the same as stripping all tags!

                Allowed tags: b, br, p, i, li, ul, ol, u, div, strong, span, em, table
                Removes: script, a, and all other tags
                """
                if not text:
                    return ""

                text = str(text)
                # C#'s valid_tags list (Data.cs:180) is declared but never
                # applied, so it strips nothing by allowlist. The API does reject
                # unknown tags, so we enforce one - but it has to include the
                # table children, or "<table>" survives with its rows gone.
                allowed_tags = {'b', 'br', 'p', 'i', 'li', 'ul', 'ol', 'u', 'div',
                                'strong', 'span', 'em',
                                'table', 'thead', 'tbody', 'tfoot', 'tr', 'td', 'th'}

                # Self-closing breaks are dropped outright, before anything else
                # normalises them - Data.cs:177 removes "<br/>" rather than
                # turning it into "<br>".
                text = re.sub(r'<br\s*/>', '', text, flags=re.IGNORECASE)

                # Anything styled bold becomes a real <b> (Data.cs:178).
                text = re.sub(r'bold.+?>(.*?)</', r'><b>\1</b></', text, flags=re.DOTALL)

                # Lowercase the whole tag, closing tags included (Data.cs:179).
                text = re.sub(r'(</?[^>]+>)', lambda m: m.group(1).lower(), text,
                              flags=re.DOTALL)

                # Remove <script> and <a> tags completely
                text = re.sub(r'<script>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
                text = re.sub(r'<a\b.*?</a>', '', text, flags=re.IGNORECASE | re.DOTALL)

                # Strip tag attributes. C# collects each opening tag's attribute
                # string and deletes every occurrence of it from the document,
                # longest first, so "<div class='x'>" ends up "<div>"
                # (Data.cs:185-212).
                attribute_strings = set()
                for match in re.finditer(r'<\w+(.*?)>', text, re.IGNORECASE | re.DOTALL):
                    attrs = match.group(1)
                    if attrs:
                        attribute_strings.add(attrs)

                for attrs in sorted(attribute_strings, key=len, reverse=True):
                    # "/" is the self-closing marker, not an attribute - C# skips it.
                    if attrs == "/":
                        continue
                    text = text.replace(attrs, "")

                # Headings become bold runs BEFORE any tag removal, otherwise
                # <h4> would be deleted as "not allowed" and its text would lose
                # all emphasis (Data.cs:227-228).
                text = re.sub(r'<h[1-6]>', '<br><br><b>', text, flags=re.IGNORECASE)
                text = re.sub(r'</h[1-6]>', '</b><br>', text, flags=re.IGNORECASE)

                # Drop tags outside the allowed set, keeping their inner text.
                # C# declares a valid_tags list but never applies it - the API
                # rejects unknown tags though, so we do enforce it here.
                def remove_disallowed_tags(text):
                    # Find all tags
                    pattern = r'</?(\w+)[^>]*>'
                    all_tags = set()
                    for match in re.finditer(pattern, text):
                        all_tags.add(match.group(1).lower())

                    # Remove disallowed opening and closing tags
                    for tag in all_tags:
                        if tag not in allowed_tags:
                            # Remove opening tags with attributes
                            text = re.sub(f'<{tag}\\b[^>]*>', '', text, flags=re.IGNORECASE)
                            # Remove closing tags
                            text = re.sub(f'</{tag}>', '', text, flags=re.IGNORECASE)

                    return text

                text = remove_disallowed_tags(text)

                # Normalize any remaining <br> variants. "</br>" is not real
                # HTML but the per-company substitutions emit it, and without
                # this it survives every later step - the allowlist keeps "br"
                # and the collapse below only matches "<br>".
                text = re.sub(r'<\s*/?\s*br\s*/?\s*>', '<br>', text, flags=re.IGNORECASE)

                # Clean up extra whitespace inside tags
                text = re.sub(r'(>\s{1,}<)', '><', text, flags=re.IGNORECASE | re.DOTALL)

                # Replace non-breaking spaces and entities
                text = text.replace('&nbsp;', ' ')
                text = text.replace('\xa0', ' ')

                # If no HTML tags remain, convert newlines to <br>
                if '<' not in text or '>' not in text:
                    text = text.replace('\r\n', '<br>')
                    text = text.replace('\n', '<br>')
                    text = text.replace('\r', '<br>')
                else:
                    # Clean up newlines when HTML is present
                    text = text.replace('<p></p>', '')
                    text = text.replace('\\n', '')
                    text = text.replace('\\t', '')
                    text = text.replace('\n', '')
                    text = text.replace('\r', '')

                # Collapse multiple <br> tags
                text = re.sub(r'(<br>){5,}', '<br><br>', text, flags=re.IGNORECASE | re.DOTALL)

                # Clean up li tags
                text = re.sub(r'</li>(<br>){1,}<li>', '</li><li>', text, flags=re.IGNORECASE | re.DOTALL)
                text=re.sub(r'<p>\s*<li>\s*','<li>',text,flags=re.IGNORECASE)
                text=re.sub(r'</p>\s*(?=<p>\s*<li>)','</li>',text,flags=re.IGNORECASE)
                # Clean up p tags
                text = text.replace('</p><br><br>', '</p>')

                # Add <br> before <table
                text = text.replace('<table', '<br><table')

                return text.strip()

            def strip_html_tags(text):
                """
                DEPRECATED: Old method that removed ALL HTML tags
                Use clean_jd() instead which keeps allowed tags

                Kept for backward compatibility with company profile cleaning
                """
                if not text:
                    return ""
                text = str(text)
                text = text.replace('<br>', '\n').replace('<BR>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
                text = re.sub(r'<[^>]*>', '', text)
                return text

            # Company profile fallback chain, mirroring Naukri.cs:1016-1025:
            #   1. [Comp Prof] from the row
            #   2. companyDetail.hotjobProfile from the operations response
            #   3. the company name
            # Never the JD - that is a separate field.
            # Prefer the name the company API returned - it is the authoritative
            # one - and fall back to the row's [Company Name]. company_details is
            # only populated by initialize(), so read it defensively.
            company_details = getattr(self, 'company_details', None)
            api_company_name = str(
                (company_details.company_name if company_details else "") or ""
            ).strip()
            company_name_for_api = api_company_name or str(job.company_name or "").strip()

            row_profile = str(job.company_profile or "").strip()

            # C# treats anything under 10 chars as "not a profile".
            if len(row_profile) >= 10:
                company_profile_for_api = clean_jd(row_profile)
            elif getattr(self, 'account_company_profile', None):
                company_profile_for_api = clean_jd(self.account_company_profile)
                logger.info(
                    f"No usable [Comp Prof] for '{job.position}'; "
                    f"using the account's hotjobProfile"
                )
            elif company_name_for_api:
                company_profile_for_api = company_name_for_api
                logger.info(
                    f"No [Comp Prof] or account profile for '{job.position}'; "
                    f"using company name as the profile"
                )
            else:
                company_profile_for_api = ""

            # Company address from the resource document, resolved in
            # initialize() (ORE.cs:556-562, used at 649).
            company_address = getattr(self, 'company_address', None) or "."

            company_detail = {
                'name': company_name_for_api or "Company",
                'websiteUrl': "",  # Would come from API resource call
                'details': company_profile_for_api,  # ORE.cs line 648: uses Comp_Profile, NOT JD
                'address': company_address,  # ORE.cs line 649: from API resource addressList, NOT JD
                'media': {
                    'video': [],
                    'photos': [],
                    'ppt': []
                },
                'size': "1-10",
                'workAreas': "",
                'fundingStage': "",
                'investorDetails': "",
                'hiringFor': ""  # Would be set if company_type == "consultant"
            }

            # Non-Metro Locations - ORE.cs lines 932-941
            non_metro_locations = {
                'nationalLocations': [],
                'internationalLocations': [],
                'locationLabels': [],
                'otherNationalLocations': [],
                'otherInternationalLocations': [],
                'locality': [],
                'localityLabels': [],
                'otherLocalities': []
            }

            # Education - ORE.cs lines 973-982 (GetEducation method lines 409-429)
            # Parse education format: "#9502:" or "#9502:spec1,spec2" -> {course, spec}
            def parse_education_value(edu_input):
                """
                Parse education value (string or list) into API format
                Input: "#9502:" or ["#9502:"] or "#9502:spec1,spec2"
                Output: [{"course": "9502", "spec": [...]}, ...]
                """
                if not edu_input:
                    return []

                # Convert to string if it's a list
                if isinstance(edu_input, list):
                    if not edu_input or not edu_input[0]:
                        return []
                    edu_str = str(edu_input[0])
                else:
                    edu_str = str(edu_input)

                edu_array = []
                # Split by pipe if multiple educations
                for edu_item in edu_str.replace("#", "").split("|"):
                    if not edu_item.strip():
                        continue
                    parts = edu_item.split(":")
                    edu_obj = {'course': parts[0].strip()}
                    # Add spec if provided
                    if len(parts) > 1 and parts[1].strip():
                        edu_obj['spec'] = [s.strip() for s in parts[1].split(",")]
                    else:
                        edu_obj['spec'] = []
                    edu_array.append(edu_obj)
                return edu_array

            # Kept at this scope because appliedFilters reuses them - ORE.cs:899-905
            education = {}
            ug_gid, pg_gid, ppg_gid = [], [], []
            degree_combination = ""
            if job.education:
                # Parse education values
                ug_gid = parse_education_value(job.education.ug_gid) if job.education.ug_gid else []
                pg_gid = parse_education_value(job.education.pg_gid) if job.education.pg_gid else []
                ppg_gid = parse_education_value(job.education.ppg_gid) if job.education.ppg_gid else []

                # Build degreeCombination - ORE.cs lines 574-580
                # Add "ug", "pg", "ppg" to list if they have values, join with "or"
                degree_list = []
                if ug_gid:
                    degree_list.append("ug")
                if pg_gid:
                    degree_list.append("pg")
                if ppg_gid:
                    degree_list.append("ppg")
                degree_combination = "or".join(degree_list) if degree_list else ""

                education = {
                    'ugGid': ug_gid,
                    'pgGid': pg_gid,
                    'ppgGid': ppg_gid,
                    'degreeCombination': degree_combination
                }

            # Walk-in Detail - ORE.cs lines 987-1000
            walk_in_detail = {
                'walkinStartDate': "",
                'saturdayWorking': "true",
                'sundayWorking': "true",
                'walkinEndDate': "",
                'dailyTiming': "9.30 AM - 5.30 PM",
                'venueAddress': "",
                'mapUrl': "",
                'embedMapUrl': "",
                'contactName': "",
                'contactPhone': ""
            }

            # Salary Detail - ORE.cs lines 1007-1015
            salary_detail = {}
            if job.salary_detail:
                salary_detail = {
                    'minimumSalary': int(job.salary_detail.minimum_salary),
                    'maximumSalary': int(job.salary_detail.maximum_salary),
                    'currency': job.salary_detail.currency,
                    'hideSalary': True,  # Default to True per user requirement
                    'variablePercentage': 0
                }

            # Response Manager - ORE.cs lines 597-620
            # Mode comes from [Responses]; settings shape depends on the mode.
            response_manager_type, response_manager_settings = self.build_response_manager(job)

            # assignedSubUsers only when mode is rms - Naukri.cs:1104-1130, ORE.cs:666-667
            assigned_sub_users = self.resolve_assigned_sub_users(response_manager_type)

            # appliedFilters (PAF) - ORE.cs lines 792-920, 1028
            applied_filters = self.build_applied_filters(
                job,
                national_locations_gid=national_locations_gid,
                international_locations_gid=international_locations_gid,
                ug_gid=ug_gid,
                pg_gid=pg_gid,
                ppg_gid=ppg_gid,
                degree_combination=degree_combination,
            )

            # Build main job object - ORE.cs lines 665-1028
            # Main description field: Clean JD (keep allowed tags, remove disallowed)
            # This matches C# Data.CleanJD logic (Data.cs:171-234)
            desc_for_job = job.description or "Job Description"
            desc_for_job = clean_jd(desc_for_job)

            job_payload = {
                'createdDate': int(datetime.now().timestamp() * 1000),
                'jobState': action,
                'mode': 'jp',
                'draftId': None,
                'jobId': job.job_id if action == ACTION_UPDATE else None,
                'editBoard': None,
                'boardProprietaryJobType': None,
                'source': 'offline',
                'jobType': 'fulltime',
                'companyType': 'established',
                'internshipStartDate': "",
                'internshipDuration': "",
                'internshipDeadline': "",
                'internshipPpo': False,
                'title': job.position,
                # wfhType is added below only when [WFH] has a value - ORE.cs:684-687
                'requirementName': job.requirement_name if job.requirement_name and hasattr(job, 'responses') and 'RMSENTER' in str(job.responses or "") else "",
                'description': desc_for_job,
                # Job-type specific fields - ORE.cs lines 699-710
                'dcp': clean_html_content(job.desired_candidate_profile) if job.job_type == 'c' else "",
                'jpb': "" if job.job_type == 'c' else "",
                'rnr': clean_html_content(job.description) if job.job_type == 'c' else ".",
                'keySkillsGid': key_skills_gid,
                # C# assigns the string MinExp/MaxExp to all four - ORE.cs:736-739
                'minimumExperience': str(job.min_experience),
                'maximumExperience': str(job.max_experience),
                'minimumExperienceLabel': str(job.min_experience),
                'maximumExperienceLabel': str(job.max_experience),
                'isRmj': False,
                'walkIn': "false",
                'walkInDetail': walk_in_detail,
                'nationalLocationsGid': national_locations_gid,
                'internationalLocationsGid': international_locations_gid,
                'otherNationalLocations': job.other_national_locations or [],
                'otherInternationalLocations': job.other_international_locations or [],
                'localities': {},
                'localitiesGid': job.localities_gid or {},
                'otherLocalities': [],
                'companyId': self.company_id,
                'nonMetroLocations': non_metro_locations,
                'microsites': [],
                'companyDetail': company_detail,
                'category': job.job_type,
                'referenceCode': job.reference_code or "",
                'vacancy': "" if job.vacancy is None else job.vacancy,  # ORE.cs:951
                'employmentType': 'Full Time, Permanent',  # Exact string from C#
                'industryGid': job.industry_gid.split('-')[0].strip() if job.industry_gid and '-' in job.industry_gid else job.industry_gid,
                'subIndustryGid': job.industry_gid.split('-')[1].strip() if job.industry_gid and '-' in job.industry_gid else "",
                'functionalArea': job.functional_area_gid,
                'functionalAreaGid': job.functional_area_gid,
                'roleCategoryGid': job.role_category_gid or "",
                'jobRole': job.job_role_gid or "",
                'jobRoleGid': job.job_role_gid or "",
                'education': education,
                'recruiterProfile': None,
                'showRecruiterDetail': False,
                'allowSendQuery': None,
                'salaryDetail': salary_detail,
                'questionnaireId': None,
                'responseManager': response_manager_type,
                'responseManagerSettings': response_manager_settings,
                'requirementId': "",
                'registrationType': 'consultant' if company_type == 'consultant' else 'company',
                'selectedBoards': [1],
                'initialSelectedLocationCount': None,
                'shareJobLegacyFlag': False,
                'appliedFilters': applied_filters,  # ORE.cs:1028
            }

            # wfhType is only sent when [WFH] has a value - ORE.cs:684-687
            if job.wfh:
                job_payload['wfhType'] = str(job.wfh)

            # baseLocation key is only present when the WFH condition holds - ORE.cs:778-787
            if base_location is not None:
                job_payload['baseLocation'] = base_location

            # Add S-type specific fields if needed
            if job.job_type == 's':
                job_payload['qualification'] = []
                job_payload['freeJob'] = 1
                job_payload['subCategoryType'] = 'basic'
                job_payload['otherIndustry'] = ""

            # Add assignment only when non-empty - ORE.cs:666-667 omits the key otherwise
            if assigned_sub_users:
                job_payload['assignedSubUsers'] = assigned_sub_users
                job.assigned_sub_users = assigned_sub_users

            # Build boards object - ORE.cs lines 624-638
            boards = {
                '1': {
                    'boardProprietaryJobType': None,
                    'responseManager': response_manager_type,
                    'responseManagerSettings': response_manager_settings
                }
            }

            # Add job-type specific fields to boards for c-type - ORE.cs lines 630-638
            if job.job_type == 'c':
                # For c-type boards: Use clean JD, then convert remaining <br> to \n (ORE.cs 633-634)
                boards_desc = job.description or "Job Description"
                boards_desc = clean_jd(boards_desc)  # Clean first (keep allowed tags)
                # Then convert <br> to \n for board display
                boards_desc = boards_desc.replace("<br>", "\n")
                # Strip any remaining HTML tags (shouldn't be many after clean_jd)
                boards_desc = re.sub(r'<[^>]*>', '', boards_desc)

                boards['1']['description'] = boards_desc
                boards['1']['dcp'] = clean_html_content(job.desired_candidate_profile) or ""
                boards['1']['jpb'] = ""
                boards['1']['rnr'] = boards_desc

            # Build draft save payload - ORE.cs lines 1032-1039
            draft_payload = {
                'primaryKey': "136",
                'draftName': job.requirement_name or job.position,
                'secondaryKey': "naukriIndia",
                'tertiaryKey': str(self.company_id),
                'id': None,
                'job': job_payload,
                'boards': boards
            }

            # Build publish payload - ORE.cs lines 1085-1090
            publish_payload = {
                'boards': boards,
                'draftId': None,  # Will be set after draft save
                'job': job_payload
            }


            logger.info(f"Prepared job payload for {job.position}")
            return draft_payload, publish_payload

        except JobPostingValidationError:
            # A pre-flight check failed; let post_job report the real reason.
            raise
        except Exception as e:
            logger.error(f"Error preparing job payload: {str(e)}")
            logger.error(f"Exception details: {str(e)}", exc_info=True)
            return {}, {}

    @retry_on_exception()
    def post_job(self, job: Job, action: str = ACTION_SAVE) -> JobPostingResult:
        """
        Post a single job

        Args:
            job: Job object to post
            action: Action type

        Returns:
            JobPostingResult with status
        """
        start_time = datetime.now()
        result = JobPostingResult(
            success=False,
            original_job_id=job.job_id,
            company_id=self.company_id,
            job_sent_id=job.job_sent_id,
            posted_title=job.position,
        )

        try:
            logger.info(
                f"Starting job posting for [Sr No: {job.job_sent_id}] "
                f"{job.position} (Job ID: {job.job_id})"
            )

            # Step 1: only "Valid" titles are posted. Anything else is left for a
            # human: the row is marked Pending and skipped.
            title_status = TitleValidator.validate_job_title(job.position)
            if title_status != "Valid":
                logger.warning(f"[Sr No: {job.job_sent_id}] Title rejected for '{job.position}': {title_status}")
                result.errors.append(title_status)
                result.message = title_status
                self._mark_invalid_title(job, title_status, result=result)
                return result

            # Validate job
            is_valid, errors = job.validate()
            if not is_valid:
                result.errors.extend(errors)
                result.message = "Job validation failed"
                logger.error(f"Validation failed: {errors}")
                return result

            # Apply business rules
            is_valid, business_errors = self.processor.apply_business_rules(job)
            if not business_errors:
                result.errors.extend(business_errors)

            # Prepare payloads (both draft save and publish)
            # TODO: Fetch company_type from API or database
            company_type = "company"  # Default, should be fetched from GetJobResource() API
            try:
                draft_payload, publish_payload = self.prepare_job_payload(job, action, company_type)
            except JobPostingValidationError as e:
                logger.error(f"Pre-flight check failed for '{job.position}': {str(e)}")
                result.message = str(e)
                result.errors.append(str(e))
                return result
            if not draft_payload or not publish_payload:
                result.message = "Failed to prepare job payload"
                return result

            # Save draft with company_id and user_id as query parameters
            logger.info("Saving job draft...")
            draft_id = self.api_client.save_job_draft(draft_payload, company_id=self.company_id, user_id=self.user_id, offline_user=self.user_id)
            if not draft_id:
                result.message = "Failed to save job draft"
                return result

            logger.info(f"Draft saved with ID: {draft_id[:12]}...")

            # Set draft ID in publish payload
            publish_payload['draftId'] = draft_id
            publish_payload['job']['draftId'] = draft_id

            # sourcePlatform is added only after the draft save, so it rides along
            # on the publish request but never the draft - ORE.cs:1082
            publish_payload['job']['sourcePlatform'] = SOURCE_PLATFORM

            # Publish job with company_id and user_id as query parameters
            logger.info("Publishing job...")
            success, new_job_id, error_msg = self.api_client.publish_job(publish_payload, company_id=self.company_id, user_id=self.user_id, offline_user=self.user_id)

            if success and new_job_id:
                # Make job live (skip in test mode)
                if self.test_mode:
                    logger.info(f"[TEST MODE] Skipping make_live API call for job {new_job_id}")
                    result.success = True
                    result.new_job_id = new_job_id
                    result.message = f"Job posted successfully (ID: {new_job_id}) [TEST MODE - not made live]"
                    logger.info(f"[Sr No: {job.job_sent_id}] Job posted successfully: {new_job_id}")
                else:
                    logger.info(f"Making job {new_job_id} live...")
                    live_success, live_msg = self.api_client.make_live(
                        new_job_id, self.company_id, self.user_id, self.user_id
                    )

                    if live_success:
                        result.success = True
                        result.made_live = True
                        result.new_job_id = new_job_id
                        result.message = f"Job posted and made live (ID: {new_job_id})"
                        logger.info(f"[Sr No: {job.job_sent_id}] Job made live successfully: {new_job_id}")
                    else:
                        # The job exists on Naukri but is not live, so the row must
                        # not be marked Posted - it needs a human to finish it.
                        result.success = False
                        result.new_job_id = new_job_id
                        result.errors.append(f"make_live failed: {live_msg}")
                        result.message = f"Job posted but make_live failed: {live_msg}"
                        logger.error(
                            f"[Sr No: {job.job_sent_id}] Job {new_job_id} posted but "
                            f"make_live FAILED ({live_msg}) - row NOT marked Posted"
                        )
            else:
                result.message = error_msg or "Unknown publishing error"
                result.errors.append(result.message)
                logger.error(f"[Sr No: {job.job_sent_id}] Job publishing failed: {error_msg}")

                # A title the API rejects needs the same treatment as one the
                # local gate rejects: back to Pending for a human, so it does
                # not sit unmarked and get retried unchanged on the next run.
                if self._is_title_rejection(error_msg):
                    logger.warning(
                        f"[Sr No: {job.job_sent_id}] Publish rejected the TITLE - "
                        f"marking Pending: {error_msg}"
                    )
                    self._mark_invalid_title(
                        job, "Invalid (API)", self._title_error_comment(error_msg),
                        result=result
                    )

        except Exception as e:
            result.message = f"Exception during posting: {str(e)}"
            result.errors.append(str(e))
            logger.error(f"[Sr No: {job.job_sent_id}] Job posting exception: {str(e)}")

        finally:
            end_time = datetime.now()
            result.posting_timestamp = start_time
            result.posting_duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return result

    def post_jobs_bulk(self, job_requests: List[JobPostingRequest],
                      max_workers: int = 5, action: str = ACTION_SAVE) -> BulkPostingResult:
        """
        Post multiple jobs concurrently

        Args:
            job_requests: List of job posting requests
            max_workers: Maximum concurrent jobs
            action: Action type

        Returns:
            BulkPostingResult with summary
        """
        logger.info(f"Starting bulk job posting: {len(job_requests)} jobs")

        bulk_result = BulkPostingResult(
            total_jobs=len(job_requests),
            start_time=datetime.now()
        )

        posted_jobs = 0
        failed_jobs = 0

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_request = {}

                # Submit all jobs
                for idx, request in enumerate(job_requests):
                    try:
                        # Build job object
                        job, errors = self.job_builder.build_from_request(request)

                        if errors:
                            result = JobPostingResult(
                                success=False,
                                original_job_id=request.job_id,
                                company_id=request.company_id,
                                errors=errors,
                                message="Failed to build job object"
                            )
                            bulk_result.results.append(result)
                            failed_jobs += 1
                            continue

                        # Submit to executor
                        future = executor.submit(self.post_job, job, action)
                        future_to_request[future] = request

                    except Exception as e:
                        logger.error(f"Failed to submit job {idx}: {str(e)}")
                        result = JobPostingResult(
                            success=False,
                            original_job_id=request.job_id,
                            company_id=request.company_id,
                            errors=[str(e)],
                            message="Failed to submit job"
                        )
                        bulk_result.results.append(result)
                        failed_jobs += 1

                # Collect results
                for future in as_completed(future_to_request):
                    try:
                        result = future.result()
                        bulk_result.results.append(result)

                        if result.success:
                            posted_jobs += 1
                            logger.info(f"Job posted: {result.new_job_id}")
                            request = future_to_request[future]
                            # Written back as-is: nothing in the pipeline rewrites
                            # the title, and rebuilding the location from the
                            # mapped Location objects would silently drop any
                            # location that failed Excel mapping.
                            result.posted_location = str(
                                request.extract_field('Location', '') or ""
                            )
                            result.all_info = self.build_all_info(
                                request,
                                result.posted_title,
                                result.posted_location,
                            )
                            self._mark_job_posted(result)
                        else:
                            failed_jobs += 1
                            logger.warning(f"Job failed: {result.message}")

                    except Exception as e:
                        logger.error(f"Exception retrieving result: {str(e)}")
                        failed_jobs += 1

            bulk_result.successful_jobs = posted_jobs
            bulk_result.failed_jobs = failed_jobs
            bulk_result.end_time = datetime.now()

            logger.info(f"Bulk posting complete: {posted_jobs} successful, {failed_jobs} failed")

        except Exception as e:
            logger.error(f"Bulk posting exception: {str(e)}")
            bulk_result.failed_jobs = len(job_requests)

        return bulk_result

    def cleanup(self):
        """Cleanup resources"""
        try:
            self.api_client.close()
            logger.info("JobPoster cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
