"""
Job Processing and Business Logic Module
"""

import re
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
from models import Job, JobPostingRequest, Location, Education, SalaryDetail, KeySkill, ResponseManagerSettings
import pandas as pd

logger = logging.getLogger(__name__)

# Per-company JD clean-up, applied in order - each rule sees the previous one's
# output. Excel's SUBSTITUTE() nests inside-out, so the innermost call runs
# first; these are already flattened into execution order.
#
# Sequences like "â€¢" and "â?¢" are deliberate: the source JDs carry
# mojibake from a UTF-8/CP1252 round trip (a bullet, an en-dash, a curly
# apostrophe). We match the corrupted bytes exactly as they arrive, so do not
# "correct" them to real Unicode.
# Companies whose JDs get a leading "Job Description" heading removed, and whose
# experience is read out of the JD rather than the [Exp] column.
STRIP_LEADING_JD_HEADING = {"27117"}
EXTRACT_EXP_FROM_JD_COMPANIES = {"27117"}

COMPANY_JD_SUBSTITUTIONS = {
    # Generated from the =TRIM(CLEAN(SUBSTITUTE(...))) formula for this account.
    "27117": [
        ('âasadasda1223€“', '–'),
        ('\\n - ', '</li><li>'),
        ('<br/>', '<br>'),
    ],
}


class JobValidator:
    """Validates job data against business rules"""

    @staticmethod
    def validate_title(title: str) -> Tuple[bool, Optional[str]]:
        """
        Validate job title

        Returns:
            (is_valid, error_message)
        """
        if not title or len(title.strip()) == 0:
            return False, "Job title cannot be empty"

        if len(title) > 70:
            return False, "Job title cannot exceed 70 characters"

        # Check for invalid characters
        invalid_chars = r'[<>:"/\\|?*]'
        if re.search(invalid_chars, title):
            return False, "Job title contains invalid characters"

        return True, None

    @staticmethod
    def validate_keywords(keywords: List[str], mandatory_keywords: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate keywords

        Returns:
            (is_valid, error_message)
        """
        if not keywords or len(keywords) < 3:
            return False, "Minimum 3 keywords are required"

        if len(keywords) > 10:
            return False, "Maximum 10 keywords allowed"

        if mandatory_keywords and len(mandatory_keywords) > 5:
            return False, "Maximum 5 mandatory keywords allowed"

        return True, None

    @staticmethod
    def validate_locations(national_locs: List[Location], intl_locs: List[Location]) -> Tuple[bool, Optional[str]]:
        """
        Validate location selection

        Returns:
            (is_valid, error_message)
        """
        total_locs = len(national_locs) + len(intl_locs)

        if total_locs == 0:
            return False, "At least one location is required"

        if total_locs > 3:
            return False, "Only 3 primary locations are allowed (rest should be in 'Other Locations')"

        return True, None

    @staticmethod
    def validate_experience(min_exp: int, max_exp: int) -> Tuple[bool, Optional[str]]:
        """
        Validate experience range

        Returns:
            (is_valid, error_message)
        """
        if min_exp < 0:
            return False, "Minimum experience cannot be negative"

        if min_exp > 30:
            return False, "Minimum experience cannot exceed 30 years"

        if max_exp < min_exp:
            return False, "Maximum experience must be greater than minimum experience"

        return True, None

    @staticmethod
    def validate_education(education: Education) -> Tuple[bool, Optional[str]]:
        """
        Validate education requirements

        Returns:
            (is_valid, error_message)
        """
        if not education:
            return False, "Education requirements are mandatory"

        has_ug = education.ug_gid and len(education.ug_gid) > 0
        has_pg = education.pg_gid and len(education.pg_gid) > 0
        has_ppg = education.ppg_gid and len(education.ppg_gid) > 0

        if not has_ug:
            return False, "Undergraduate degree is required"

        return True, None


class JobProcessor:
    """Processes job data and applies business logic"""

    def __init__(self, location_mapping_df: pd.DataFrame = None, industry_mapping_df: pd.DataFrame = None,
                 junk_words: Dict[str, List[str]] = None):
        """
        Initialize processor with optional location and industry mapping

        Args:
            location_mapping_df: DataFrame with location ID to name mapping
            industry_mapping_df: DataFrame with industry label to ID mapping
            junk_words: {company_id: [phrase, ...]} from crawler.junk
        """
        self.location_mapping = location_mapping_df
        self.industry_mapping = industry_mapping_df
        self.junk_words = junk_words or {}
        self.validator = JobValidator()

    def map_industry_label_to_id(self, industry_label: str) -> Optional[str]:
        """
        Map industry label to numeric ID using industry mapping

        Mirrors C# ReadExcel logic (RibbonController.cs line 544):
        - Column 0 (indtype): ID like "8", "32", "101 -"
        - Column 1 (Industry): Label like "Accounting / Finance"

        Database provides industry_label, we search for it in Industry column and return indtype

        Args:
            industry_label: Industry name/label from database (e.g., "IT Services & Consulting")

        Returns:
            Industry numeric ID (e.g., "109 -") or None if not found
        """
        if self.industry_mapping is None or self.industry_mapping.empty:
            logger.warning(f"No industry mapping available for '{industry_label}'")
            return None

        try:
            industry_label_clean = industry_label.strip() if industry_label else ""
            if not industry_label_clean:
                return None

            # Match in Industry column (column 1) and return indtype (column 0)
            # C# uses .Contains() for partial matching, replicate that behavior
            for idx, row in self.industry_mapping.iterrows():
                industry_col_value = str(row.get('Industry', '') or '').strip()

                # Match: exact or partial (C# uses .Contains behavior)
                if industry_col_value.lower() == industry_label_clean.lower() or \
                   industry_label_clean.lower() in industry_col_value.lower():
                    indtype_value = str(row.get('indtype', '')).strip()
                    if indtype_value:
                        logger.debug(f"Industry '{industry_label_clean}' -> indtype '{indtype_value}'")
                        return indtype_value

            logger.warning(f"Industry '{industry_label}' not found in mapping")
            return None
        except Exception as e:
            logger.error(f"Error mapping industry '{industry_label}': {str(e)}")
            return None

    def map_location_name_to_id(self, location_name: str) -> Optional[int]:
        """
        Map location name to location ID using location mapping

        Args:
            location_name: Location name (e.g., "Gurugram", "Bangalore")

        Returns:
            Location ID or None if not found
        """
        if self.location_mapping is None or self.location_mapping.empty:
            logger.warning(f"No location mapping available for '{location_name}'")
            return None

        try:
            # Try to find exact match (case-insensitive)
            loc_name_lower = location_name.lower().strip()

            # Check if location_mapping has 'label' or 'name' column
            label_col = 'label' if 'label' in self.location_mapping.columns else 'name' if 'name' in self.location_mapping.columns else None
            id_col = 'id' if 'id' in self.location_mapping.columns else None

            if not label_col or not id_col:
                logger.error(f"Location mapping missing required columns. Available: {self.location_mapping.columns.tolist()}")
                return None

            # Find matching location
            matching = self.location_mapping[
                self.location_mapping[label_col].str.lower().str.strip() == loc_name_lower
            ]

            if not matching.empty:
                loc_id = matching.iloc[0][id_col]
                logger.debug(f"Mapped '{location_name}' to location ID: {loc_id}")
                return loc_id
            else:
                logger.warning(f"Location '{location_name}' not found in mapping")
                return None

        except Exception as e:
            logger.error(f"Error mapping location '{location_name}': {str(e)}")
            return None

    def apply_company_jd_substitutions(self, jd_text: str, company_id: str) -> str:
        """
        Apply the per-company JD clean-up substitutions.

        Port of the nested SUBSTITUTE() formula. Order matters: each replacement
        runs on the output of the previous one, exactly as the formula nests, so
        e.g. "<br/>-" must be handled before "<br/><b>" gets its extra break.

        Args:
            jd_text: Raw job description
            company_id: Company the row belongs to

        Returns:
            The substituted JD, or the input unchanged when the company has no rules
        """
        if not jd_text:
            return jd_text

        rules = COMPANY_JD_SUBSTITUTIONS.get(str(company_id))
        if not rules:
            return jd_text

        result = str(jd_text)
        for find, replace in rules:
            result = result.replace(find, replace)

        # The formula wraps everything in TRIM(CLEAN(...)).
        # CLEAN removes non-printing control characters - tab, CR and LF
        # included, which is why rule 28 has to convert newlines to list items
        # before this point.
        result = ''.join(c for c in result if ord(c) >= 32)
        # TRIM collapses runs of spaces to a single space and strips the ends.
        result = re.sub(r' {2,}', ' ', result).strip()

        result = self._collapse_list_markers(result)

        if result != str(jd_text):
            logger.info(f"Applied {len(rules)} JD substitutions for company {company_id}")

        return result

    @staticmethod
    def _collapse_list_markers(jd_text: str) -> str:
        """
        Collapse runs of adjacent list markers down to one.

        Source JDs often carry a bullet at the end of one item AND the start of
        the next ("... reconciliations * * Supporting ..."), so converting each
        bullet to a marker yields doubles. A fixed substitution cannot catch
        these - the separator varies (no space, one space, several) and runs can
        be longer than two - so collapse them once here instead.

        A trailing marker with nothing after it is dropped entirely.

        Args:
            jd_text: JD after the substitution rules have run

        Returns:
            The JD with duplicate markers merged
        """
        if not jd_text:
            return jd_text

        # One marker is <li> or </li><li>, optionally followed by whitespace.
        marker = r'(?:</li>)?<li>\s*'
        # Two or more in a row become a single <li>.
        collapsed = re.sub(r'(?:' + marker + r'){2,}', '<li>', jd_text,
                           flags=re.IGNORECASE)
        # A marker left dangling at the very end opens an empty bullet.
        collapsed = re.sub(r'(?:' + marker + r')+$', '', collapsed,
                           flags=re.IGNORECASE).rstrip()

        return collapsed

    def strip_leading_job_description_heading(self, jd_text: str, company_id: str) -> str:
        """
        Drop a "Job Description" heading sitting at the very top of the JD.

        Only for the companies listed in STRIP_LEADING_JD_HEADING, and only at
        the start - an occurrence further down is real content and is kept.

        The heading arrives in many shapes across rows, so rather than listing
        wrappers this walks the opening tags: skip any run of opening tags and
        break/space filler, and if the first actual text is "Job Description"
        (optionally followed by a colon), drop that text plus the tags that
        wrapped only it. Leaves the rest of the markup untouched.

        Args:
            jd_text: Job description
            company_id: Company the row belongs to

        Returns:
            The JD without the leading heading
        """
        if not jd_text or str(company_id) not in STRIP_LEADING_JD_HEADING:
            return jd_text or ""

        jd = str(jd_text)

        # Filler that can precede or surround the heading text.
        filler = r'(?:\s|&nbsp;|<br\s*/?>|</br>)*'
        # Any opening tag, e.g. <h4>, <p class="x">, <span>, <b>.
        open_tag = r'<[a-zA-Z][^>/]*>'

        # The heading must be followed by a colon or a tag - never by more words,
        # so "Job Description Analyst" is left alone.
        pattern = re.compile(
            r'^'
            + filler
            + r'(?:' + open_tag + filler + r')*'      # opening tags before it
            + r'job\s*description'                    # the heading text itself
            + r'\s*(?::|(?=<|$))'                     # colon, or a tag/end follows
            + filler
            + r'(?:</[a-zA-Z][^>]*>' + filler + r')*',  # closing tags after it
            re.IGNORECASE,
        )

        match = pattern.match(jd)
        if not match:
            return jd

        remainder = jd[match.end():]

        logger.info(
            f"Removed leading 'Job Description' heading for company {company_id}"
        )
        return remainder.lstrip()

    def clean_jd_spaces(self, jd_text: str) -> str:
        """
        Swap paragraph tags for divs.

        Port of Data.CleanJdSpaces - <p>/</p> become <div>/</div>, case
        insensitively.

        Args:
            jd_text: Job description

        Returns:
            The JD with paragraph tags replaced
        """
        if not jd_text:
            return ""

        jd = str(jd_text)
        jd = re.sub(r"<p>", "<div>", jd, flags=re.IGNORECASE | re.DOTALL)
        jd = re.sub(r"</p>", "</div>", jd, flags=re.IGNORECASE | re.DOTALL)
        return jd

    def clean_junk(self, jd_text: str, company_id: str) -> str:
        """
        Strip the company's junk phrases from the JD.

        Port of Data.CleanJunk: every phrase registered against this company in
        crawler.junk is removed, case insensitively, repeatedly until gone.

        Args:
            jd_text: Job description
            company_id: Company the row belongs to

        Returns:
            The JD with junk removed, unchanged when the company has no entries
        """
        if not jd_text or not self.junk_words:
            return jd_text or ""

        phrases = self.junk_words.get(str(company_id))
        if not phrases:
            return jd_text

        jd = str(jd_text)
        removed = 0
        for phrase in phrases:
            if not phrase:
                continue
            # Case-insensitive removal of every occurrence (ReplaceCase loops
            # until IndexOf stops finding the phrase).
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            jd, count = pattern.subn("", jd)
            removed += count

        if removed:
            logger.info(f"Removed {removed} junk phrase(s) from JD for company {company_id}")

        return jd

    def extract_exp_range_from_jd(self, jd_text: str) -> Optional[Tuple[int, int]]:
        """
        Pull an experience range out of the job description.

        Port of the ExtractExpRange VBA function. Strips HTML, normalises the
        many broken spellings of "year(s)", then tries three patterns in
        priority order, stopping at the first that yields a match:

          0. "minimum X years"           -> X to X+5
          1. "years of experience: X to Y"
          2. any "X to Y years" / "X+ years" / "X years"

        Priorities 0 and 2 skip matches whose surrounding text is about
        education rather than experience.

        Args:
            jd_text: Raw job description, HTML included

        Returns:
            (min_exp, max_exp), or None when nothing matched ("Not Found")
        """
        if not jd_text:
            return None

        # --- STEP 1: strip HTML ---
        cleaned = str(jd_text)
        cleaned = cleaned.replace("<br/>", " ").replace("<br>", " ").replace("&nbsp;", " ")
        cleaned = re.sub(r"<[^>]*>", " ", cleaned)

        # --- STEP 2: normalise ---
        cleaned = cleaned.replace("\r", " ").replace("\n", " ")
        for broken, fixed in (
            ("year(s)", "years"),
            ("year (s)", "years"),
            ("year  s", "years"),
            ("year    s", "years"),
            ("year s of", "years of"),
            ("year s experience", "years experience"),
            ("year s", "years"),
            ("year experience", "years"),
        ):
            cleaned = cleaned.replace(broken, fixed)
        # VBA's Application.Trim also collapses runs of interior spaces.
        cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()

        def has_education_context(start: int, words: Tuple[str, ...]) -> bool:
            """Look at the text around a match the way the VBA Mid() does."""
            ctx_start = max(0, start - 60)
            context = cleaned[ctx_start:ctx_start + 150]
            return any(w in context for w in words)

        min_exp, max_exp = -1, -1

        # --- PRIORITY 0: "minimum X years" ---
        for m in re.finditer(r"minimum\s*([0-9]+(\.[0-9]+)?)\s*year[s]?", cleaned):
            if has_education_context(m.start(), ("education", "qualification")):
                continue
            temp_min = int(float(m.group(1)))
            temp_max = temp_min + 5
            if temp_max > max_exp:
                min_exp, max_exp = temp_min, temp_max

        # --- PRIORITY 1: "years of experience: X to Y" ---
        if min_exp == -1:
            for m in re.finditer(
                r"years of experience[:\s]*([0-9]+)\s*(to|\-)\s*([0-9]+)", cleaned
            ):
                temp_min = int(m.group(1))
                temp_max = int(m.group(3))
                if temp_min == 0:
                    temp_max = 1
                if temp_max > max_exp:
                    min_exp, max_exp = temp_min, temp_max

        # --- PRIORITY 2: generic patterns ---
        if min_exp == -1:
            pattern = r"([0-9]+(\.[0-9]+)?)\s*(\+|to|\-)?\s*([0-9]+(\.[0-9]+)?)?\s*year[s]?"
            for m in re.finditer(pattern, cleaned):
                if has_education_context(
                    m.start(),
                    ("education", "qualification", "degree", "bachelor", "master"),
                ):
                    continue

                value = m.group(0)
                if "to" in value or "-" in value:
                    parts = value.split("to") if "to" in value else value.split("-")
                    temp_min = self._vba_val(parts[0])
                    temp_max = self._vba_val(parts[1]) if len(parts) > 1 else 0
                    if temp_min == 0:
                        temp_max = 1
                elif "+" in value:
                    temp_min = self._vba_val(value)
                    temp_max = temp_min + 5
                else:
                    temp_min = self._vba_val(value)
                    temp_max = temp_min + 5

                if temp_min == temp_max:
                    temp_max = temp_min + 5
                if temp_max < temp_min:
                    temp_max = temp_min + 5

                if temp_max > max_exp:
                    min_exp, max_exp = temp_min, temp_max

        if min_exp == -1:
            return None

        logger.info(f"Experience from JD: {min_exp}-{max_exp} yrs")
        return min_exp, max_exp

    @staticmethod
    def _vba_val(text: str) -> int:
        """
        Mimic VBA Val(): read the leading numeric run and ignore the rest.

        Val(" 5 years") is 5 and Val("years") is 0, so a non-numeric string
        yields 0 rather than raising.
        """
        match = re.match(r"\s*([0-9]+(\.[0-9]+)?)", str(text))
        return int(float(match.group(1))) if match else 0

    def parse_experience(self, exp_str: str) -> Tuple[int, int]:
        """
        Parse experience string to min/max values

        Args:
            exp_str: Experience string (e.g., "2-5 years", "3-8")

        Returns:
            (min_experience, max_experience)
        """
        try:
            if not exp_str:
                return 0, 0

            # Extract all numbers from string
            numbers = re.findall(r'\d+', str(exp_str))
            if len(numbers) == 0:
                return 0, 0

            min_exp = int(numbers[0])

            # Calculate max experience based on min
            if len(numbers) > 1:
                max_exp = int(numbers[1])
            else:
                if min_exp < 10:
                    max_exp = min_exp + 5
                else:
                    max_exp = min_exp + 10

            logger.info(f"Parsed experience: {exp_str} -> {min_exp}-{max_exp}")
            return min_exp, max_exp
        except Exception as e:
            logger.error(f"Error parsing experience '{exp_str}': {str(e)}")
            return 0, 0

    def resolve_response_mode(self, responses: str) -> str:
        """
        Derive the response mode from the [Responses] column.

        Mirrors Naukri.cs lines 1081-1096 exactly, including the ordering of the
        checks - "Customised URL"/anything containing "URL" wins over the email
        check, so a value like "URL - apply@x.com" is a companyUrl job.

        Args:
            responses: Raw (trimmed) [Responses] value

        Returns:
            'companyUrl', 'ATS', or 'rms' (the C# default)
        """
        responses = str(responses or "").strip()

        if responses == "Customised URL" or "URL" in responses:
            return "companyUrl"
        if "@" in responses or "E-Apps" in responses or "eapps" in responses.lower():
            return "rms"
        if responses in ("CSM", "RMS"):
            return "rms"
        if responses == "ATS":
            return "ATS"
        return "rms"

    def calculate_rating(self, paf_str: str) -> str:
        """
        Calculate the relevance rating from the [PAF] column.

        Mirrors Naukri.CalculateRating (Naukri.cs:1860-1878): pull the first run
        of digits out of the string, then band it. A missing/unparseable value
        keeps the C# default of "medium".

        Args:
            paf_str: Raw [PAF] value

        Returns:
            'low' (1-2), 'medium' (3-4), or 'high' (5+)
        """
        if not paf_str:
            return "medium"

        match = re.search(r'(\d+)', str(paf_str))
        if not match:
            return "medium"

        try:
            paf_value = int(match.group(1))
        except (TypeError, ValueError):
            return "medium"

        if 0 < paf_value <= 2:
            return "low"
        if 2 < paf_value <= 4:
            return "medium"
        if paf_value > 4:
            return "high"
        return "medium"

    def parse_salary(self, salary_str: str) -> Tuple[float, float, str]:
        """
        Parse salary string to min/max values

        Args:
            salary_str: Salary string (e.g., "10-20 LPA", "Rs. 500000-800000")

        Returns:
            (min_salary, max_salary, currency)
        """
        try:
            if not salary_str:
                return 0, 0, "INR"

            # Remove Rs. prefix
            salary_str = salary_str.replace("Rs.", "").replace("rs.", "").strip()

            # Extract all numbers
            numbers = re.findall(r'[\d.]+', salary_str)
            if len(numbers) == 0:
                return 0, 0, "INR"

            min_sal = float(numbers[0])

            # Convert if in LPA (less than 101)
            if min_sal < 101:
                min_sal = min_sal * 100000

            max_sal = 0
            if len(numbers) > 1:
                max_sal = float(numbers[1])
                if max_sal < 101 and max_sal > 0:
                    max_sal = max_sal * 100000

            logger.info(f"Parsed salary: {salary_str} -> {min_sal}-{max_sal}")
            return min_sal, max_sal, "INR"
        except Exception as e:
            logger.error(f"Error parsing salary '{salary_str}': {str(e)}")
            return 0, 0, "INR"

    def parse_keywords(self, keywords_str: str) -> List[KeySkill]:
        """
        Parse keywords string to KeySkill objects
        Note: Preferred flag is NOT set here - it's set based on mandatory_keywords list in JobBuilder

        Args:
            keywords_str: Comma-separated keywords

        Returns:
            List of KeySkill objects (all with is_preferred=False initially)
        """
        try:
            if not keywords_str:
                return []

            keywords = []
            for keyword in keywords_str.split(','):
                keyword = keyword.strip()

                if keyword:
                    # Don't set is_preferred here - it will be set based on mandatory_keywords list
                    keywords.append(KeySkill(skill_name=keyword, is_preferred=False))

            logger.info(f"Parsed keywords: {keywords_str} -> {len(keywords)} skills")
            return keywords
        except Exception as e:
            logger.error(f"Error parsing keywords '{keywords_str}': {str(e)}")
            return []

    def fill_blanks(self, job: Job, defaults: Dict[str, Any]) -> Job:
        """
        Fill blank/missing values in job with defaults

        Args:
            job: Job object to fill
            defaults: Dictionary of default values

        Returns:
            Updated Job object
        """
        if not job.position and defaults.get('position'):
            job.position = defaults['position']
            logger.info("Filled blank position with default")

        if not job.description and defaults.get('description'):
            job.description = defaults['description']
            logger.info("Filled blank description with default")

        if not job.functional_area_gid and defaults.get('functional_area_gid'):
            job.functional_area_gid = defaults['functional_area_gid']
            logger.info("Filled blank functional area with default")

        if not job.industry_gid and defaults.get('industry_gid'):
            job.industry_gid = defaults['industry_gid']
            logger.info("Filled blank industry with default")

        return job

    def apply_business_rules(self, job: Job) -> Tuple[bool, List[str]]:
        """
        Apply business rules and validations to job

        Returns:
            (is_valid, error_list)
        """
        errors = []

        # Validate title
        valid, error = self.validator.validate_title(job.position)
        if not valid:
            errors.append(error)

        # Validate keywords
        if job.key_skills:
            key_skill_list = list(job.key_skills.keys()) if isinstance(job.key_skills, dict) else job.key_skills
            valid, error = self.validator.validate_keywords(key_skill_list, job.mandatory_keywords)
            if not valid:
                errors.append(error)

        # Validate locations
        valid, error = self.validator.validate_locations(job.national_locations, job.international_locations)
        if not valid:
            errors.append(error)

        # Validate experience
        valid, error = self.validator.validate_experience(job.min_experience, job.max_experience)
        if not valid:
            errors.append(error)

        # Validate education
        if job.job_type == 'c':  # Corporate jobs require education
            valid, error = self.validator.validate_education(job.education)
            if not valid:
                errors.append(error)

        return len(errors) == 0, errors

    def predict_missing_fields(self, job_data: Dict[str, Any], prediction_rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict and fill missing fields using prediction rules

        Args:
            job_data: Job data dictionary
            prediction_rules: Rules for prediction

        Returns:
            Updated job data
        """
        try:
            # Predict education based on JD keywords
            if not job_data.get('education') and job_data.get('description'):
                jd = job_data['description'].lower()
                if any(keyword in jd for keyword in ['btech', 'bachelor', 'graduate', 'b.tech']):
                    job_data['education'] = {'ug_gid': {'1': {'course': '1', 'spec': []}}}
                    logger.info("Predicted education requirement from JD")

            # Predict salary range from JD
            if not job_data.get('salary') and job_data.get('description'):
                jd = job_data['description'].lower()
                salary_match = re.search(r'(\d+)\s*(?:lpa|lakhs?|l)', jd)
                if salary_match:
                    base_salary = int(salary_match.group(1))
                    job_data['salary'] = {
                        'min': base_salary * 100000,
                        'max': (base_salary + 5) * 100000
                    }
                    logger.info(f"Predicted salary from JD: {job_data['salary']}")

            return job_data
        except Exception as e:
            logger.error(f"Error in field prediction: {str(e)}")
            return job_data


class JobBuilder:
    """Builds complete Job object from raw request data"""

    def __init__(self, processor: JobProcessor):
        """
        Initialize with JobProcessor

        Args:
            processor: JobProcessor instance for data processing
        """
        self.processor = processor

    def build_from_request(self, request: JobPostingRequest) -> Tuple[Job, List[str]]:
        """
        Build Job object from JobPostingRequest

        Returns:
            (Job object, error_list)
        """
        errors = []
        job = Job()

        try:
            # Log available fields for debugging
            available_fields = list(request.row_data.keys())
            logger.debug(f"Available fields in row data: {available_fields}")
            # Basic fields
            job.company_id = request.company_id
            job.job_type = request.job_type
            job.status = "draft"
            # [Sr No], aliased [Job Sent ID] - identifies the row for status writes
            # before Naukri has assigned a Job Id.
            job.job_sent_id = (request.extract_field('Job Sent ID', '') or
                               request.extract_field('Sr No', '') or None)

            # Required text fields
            job.position = request.extract_field('title', '') or request.extract_field('Position', '')
            # JD pipeline, in this order, before anything reads the JD:
            #   1. per-company SUBSTITUTE rules (27117 boilerplate, mojibake)
            #   2. drop a leading "Job Description" heading (per-company)
            #   3. tag correction (<p> -> <div>)
            #   4. junk-phrase removal from crawler.junk
            # Validation runs later, in post_job, against this cleaned text.
            job.description = request.extract_field('description', '') or request.extract_field('JD', '')
            job.description = self.processor.apply_company_jd_substitutions(
                job.description, request.company_id
            )
            job.description = self.processor.strip_leading_job_description_heading(
                job.description, request.company_id
            )
            job.description = self.processor.clean_jd_spaces(job.description)
            job.description = self.processor.clean_junk(job.description, request.company_id)
            # DB column is [Company Name]; the snake_case key never matched it.
            job.company_name = (request.extract_field('Company Name', '') or
                                request.extract_field('company_name', '') or '')
            # [Responses] drives both the RMSENTER check and the ResponseMode selection.
            # C# trims it before any comparison (Naukri.cs:565-566).
            job.responses = (request.extract_field('responses', '') or
                             request.extract_field('Responses', '') or '')
            job.responses = str(job.responses).strip() if job.responses else ''
            job.wfh = request.extract_field('wfh', '') or request.extract_field('WFH', '')  # For baseLocation conditional logic

            # Response manager inputs - RibbonController.cs:1328 maps [URL] -> ResponseURL
            job.response_url = (request.extract_field('URL', '') or
                                request.extract_field('url', '') or '')
            job.process = (request.extract_field('Process', '') or
                           request.extract_field('process', '') or '')
            job.paf_str = (request.extract_field('PAF', '') or
                           request.extract_field('paf', '') or '')
            # EmailResponse is not in the current SELECT; absent means "On every new apply" (ORE.cs:612)
            job.email_response = (request.extract_field('EmailResponse', '') or
                                  request.extract_field('Email Response', '') or '')

            # Derive ResponseMode from [Responses] - Naukri.cs:1081-1096
            job.response_mode = self.processor.resolve_response_mode(job.responses)

            # Experience: for the companies in EXTRACT_EXP_FROM_JD_COMPANIES the
            # JD is the primary source (ExtractExpRange) and [Exp] is the
            # fallback. Every other company uses [Exp] only.
            jd_exp = None
            if str(request.company_id) in EXTRACT_EXP_FROM_JD_COMPANIES:
                jd_exp = self.processor.extract_exp_range_from_jd(job.description)

            if jd_exp:
                job.min_experience, job.max_experience = jd_exp
                # Widen a single-point range so min and max are never equal.
                if job.min_experience == job.max_experience:
                    job.max_experience = job.max_experience + 5
                logger.info(
                    f"Experience taken from JD: {job.min_experience}-{job.max_experience}"
                )
            else:
                exp_str = (request.extract_field('experience', '') or
                           request.extract_field('Exp_Str', '') or
                           request.extract_field('Exp', '') or
                           request.extract_field('exp', ''))
                job.min_experience, job.max_experience = self.processor.parse_experience(exp_str)
                reason = ("no experience found in JD"
                          if str(request.company_id) in EXTRACT_EXP_FROM_JD_COMPANIES
                          else "JD extraction not enabled for this company")
                logger.info(
                    f"Experience from [Exp]='{exp_str}' -> "
                    f"{job.min_experience}-{job.max_experience} ({reason})"
                )

            # Salary parsing - check multiple column name variations from database
            salary_str = (request.extract_field('salary', '') or
                         request.extract_field('CTC_Str', '') or
                         request.extract_field('CTC', '') or
                         request.extract_field('ctc', ''))
            min_sal, max_sal, currency = self.processor.parse_salary(salary_str)
            job.salary_detail = SalaryDetail(min_sal, max_sal, currency)

            # Keywords parsing - at least 3 required (ORE.cs lines 714-733)
            # Try multiple field name variations (from database query)
            keywords_str = (request.extract_field('keywords', '') or
                           request.extract_field('Keywords', '') or
                           request.extract_field('Keyword', '') or
                           request.extract_field('KeyWords', ''))

            # Extract mandatory keywords (note: database has typo "Mandaory")
            mandatory_keywords_str = (request.extract_field('mandatory_keywords', '') or
                                     request.extract_field('Mandaory Keywords', '') or
                                     request.extract_field('mandaory_keywords', ''))

            if keywords_str:
                key_skills_list = self.processor.parse_keywords(keywords_str)
                mandatory_list = [k.strip() for k in mandatory_keywords_str.split(',') if k.strip()] if mandatory_keywords_str else []

                # The first keyword always counts as mandatory, on top of whatever
                # [Mandaory Keywords] lists. Naukri caps mandatory keywords at 5
                # (Naukri.cs:612), so an already-full list keeps what the DB gave.
                if key_skills_list:
                    first_keyword = key_skills_list[0].skill_name
                    already_mandatory = first_keyword.lower() in [m.lower() for m in mandatory_list]
                    if already_mandatory:
                        pass
                    elif len(mandatory_list) >= 5:
                        logger.warning(
                            f"First keyword '{first_keyword}' not marked mandatory - "
                            f"[Mandaory Keywords] already has {len(mandatory_list)} (limit 5)"
                        )
                    else:
                        mandatory_list.insert(0, first_keyword)
                        logger.info(f"First keyword '{first_keyword}' marked as mandatory")

                # Build key_skills with proper preferred flags
                # ALL mandatory keywords get preferred: "true"
                # Regular keywords get preferred: "false"
                job.key_skills = {}
                for ks in key_skills_list:
                    is_mandatory = ks.skill_name.lower() in [m.lower() for m in mandatory_list]
                    job.key_skills[ks.skill_name] = {
                        "label": ks.skill_name,
                        "preferred": "true" if is_mandatory else "false"
                    }

                job.mandatory_keywords = mandatory_list if mandatory_list else None
                logger.debug(f"Added {len(key_skills_list)} keywords with {len(mandatory_list)} mandatory: {keywords_str}")
            else:
                logger.warning("No keywords provided in request")

            # Education - provide defaults if not specified (ORE.cs lines 570-572)
            # Default values per C# code: UG=#9502:, PG=#9511:
            ug_val = request.extract_field('ug', '') or request.extract_field('UG', '') or "#9502:"
            pg_val = request.extract_field('pg', '') or request.extract_field('PG', '') or "#9511:"
            ppg_val = request.extract_field('ppg', '') or request.extract_field('PPG', '') or None

            job.education = Education(
                ug_gid=[ug_val] if ug_val else [],
                pg_gid=[pg_val] if pg_val else [],
                ppg_gid=[ppg_val] if ppg_val else []
            )
            logger.debug(f"Education: UG={ug_val}, PG={pg_val}, PPG={ppg_val}")

            # Locations - convert location names to Location objects
            location_str = request.extract_field('location', '') or request.extract_field('Location', '')
            if location_str:
                # Split by comma if multiple locations
                location_names = [loc.strip() for loc in str(location_str).split(',')]
                for loc_name in location_names:
                    if loc_name:
                        # Map location name to ID
                        loc_id = self.processor.map_location_name_to_id(loc_name)
                        if loc_id:
                            job.national_locations.append(Location(
                                location_id=str(loc_id),
                                location_name=loc_name,
                                is_custom_group=False
                            ))
                            logger.debug(f"Added location: {loc_name} (ID: {loc_id})")
                        else:
                            logger.warning(f"Could not map location: {loc_name}")
            else:
                logger.warning("No location provided in request")

            # Categories - Industry label to numeric ID mapping (ORE.cs line 675)
            # Database provides [Industry] as label, need to map to numeric ID via Excel
            industry_label = (request.extract_field('industry', '') or
                             request.extract_field('Industry', '') or
                             request.extract_field('Industry_Id', ''))

            if industry_label:
                # Try to map label to ID using industry mapping
                industry_id = self.processor.map_industry_label_to_id(industry_label)
                if industry_id:
                    job.industry_gid = industry_id
                else:
                    # Fallback: use label directly if mapping fails
                    job.industry_gid = industry_label
                    logger.warning(f"Could not map industry label '{industry_label}' to ID, using label as fallback")
            else:
                job.industry_gid = ""

            # Candidate Industry - Naukri.cs:677-684 maps the label to an id the
            # same way Industry does, and nulls it when shorter than 3 chars.
            # [Candidate Industry] is not in the current SELECT, so this is a
            # no-op today and starts working if the column is added.
            candidate_industry_label = (request.extract_field('Candidate Industry', '') or
                                        request.extract_field('candidate_industry', '') or '')
            candidate_industry_label = str(candidate_industry_label).strip()
            if len(candidate_industry_label) > 2:
                mapped = self.processor.map_industry_label_to_id(candidate_industry_label)
                job.candidate_industry = mapped or candidate_industry_label
            else:
                job.candidate_industry = None

            # Functional Area - ORE.cs line 565: Farea.Replace("#", "").Split('|')[0]
            farea_raw = request.extract_field('functional_area', '') or \
                       request.extract_field('Farea', '') or \
                       request.extract_field('Functional Area', '')
            if farea_raw:
                # Remove # prefix and take first part before pipe
                job.functional_area_gid = farea_raw.replace("#", "").split("|")[0].strip()
            else:
                job.functional_area_gid = ""

            # Role field - ORE.cs line 566: Role.Replace("#", "").Split('|')[0]
            # After cleaning: format is "something,roleCategoryGid,jobRoleGid"
            # Then split by comma at ORE.cs line 967-969
            role_raw = request.extract_field('role', '') or request.extract_field('Role', '')
            if role_raw:
                # First clean like in ORE.cs line 566
                role_cleaned = role_raw.replace("#", "").split("|")[0].strip()
                # Then parse by comma like ORE.cs line 967-969
                role_parts = role_cleaned.split(',')
                job.role_category_gid = role_parts[1].strip() if len(role_parts) > 1 else ""
                job.job_role_gid = role_parts[2].strip() if len(role_parts) > 2 else ""
            else:
                job.role_category_gid = ""
                job.job_role_gid = ""

            # Additional details
            job.roles_and_responsibilities = request.extract_field('rnr', '')
            job.desired_candidate_profile = request.extract_field('dcp', '')
            job.perks_and_benefits = request.extract_field('jpb', '')
            # Company profile from database [Comp Prof] - used for companyDetail.details
            job.company_profile = request.extract_field('Comp Prof', '') or request.extract_field('company_profile', '')

            # Metadata
            # referenceCode comes from [Req ID] (RibbonController.cs:1339-1340,
            # ORE.cs:950). The snake_case key never matched the column, so this
            # was always empty.
            req_id = (request.extract_field('Req ID', '') or
                      request.extract_field('reference_code', '') or '')
            # SQL numerics arrive as floats, so 12345.0 must not become "12345.0".
            if isinstance(req_id, float) and req_id.is_integer():
                req_id = int(req_id)
            job.reference_code = str(req_id).strip() if req_id != '' else ''
            job.requirement_id = request.extract_field('requirement_id', '')
            # Req_Name is generated, not read from a column (ORE.cs:554). It
            # feeds draftName and, for RMSENTER jobs, requirementName.
            job.requirement_name = (
                f"{job.position}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                if job.position else ""
            )

            logger.info(f"Built Job object for {job.company_id}")
            return job, errors

        except Exception as e:
            errors.append(f"Error building job object: {str(e)}")
            logger.error(f"Error building job: {str(e)}")
            return job, errors
