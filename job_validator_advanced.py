"""
Advanced Job Validation Module
Implements validation rules from posting guidelines (title validation, education defaults, etc.)
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Represents a validation error"""
    field: str
    error_code: str
    message: str
    severity: str = "error"  # error, warning


class TitleValidator:
    """
    Validates job titles.

    Port of the reference `validate_job_title` used by the =ValidateJobTitle()
    Excel formula. Only titles that come back "Valid" are posted; anything else
    is left for the caller to mark Pending. Keep this in step with the reference
    implementation - the lists and the check order are deliberate.
    """

    BAD_PHRASES = [
        "join", "urgent", "opportunity", "opportunities", "apply", "walk-in", "walk in",
        "opening", "openings", "requirement", "vacancy", "jobs", "title", "designation",
        "hiring now", "immediately", "looking for", "hiring", "career", "careers", "job"
    ]

    SALARY_WORDS = ["salary", "ctc", "lakh", "monthly", "lpa"]

    LOCATIONS = [
        "delhi", "new-delhi", "delhi-ncr", "anantapur", "gurgaon", "dwarka", "guntakal", "guntur",
        "hyderabad", "kakinada", "kurnool", "nellore", "nizamabad", "rajahmundry", "bangalore",
        "tirupati", "vijayawada", "visakhapatnam", "warangal", "itanagar", "guwahati", "silchar",
        "bhagalpur", "patna", "bhilai", "bilaspur", "raipur", "panaji", "vasco-da-gama", "ahmedabad",
        "anand", "ankleshwar", "bharuch", "bhavnagar", "bhuj", "gandhinagar", "gir", "jamnagar",
        "kandla", "porbandar", "rajkot", "surat", "vadodara", "valsad", "vapi", "ambala", "faridabad",
        "gurugram", "hisar", "karnal", "kurukshetra", "panipat", "rohtak", "dalhousie", "dharmasala",
        "manali", "shimla", "jammu", "srinagar", "bokaro", "dhanbad", "jamshedpur", "ranchi",
        "bengaluru", "belgaum", "ballari", "bidar", "dharwad", "kalburagi", "hubli", "kolar",
        "mangaluru", "mysuru", "kozhikode", "kochi", "ernakulam", "kannur", "kollam", "kottayam",
        "palakkad", "thrissur", "thiruvananthapuram", "bhopal", "gwalior", "indore", "jabalpur",
        "ujjain", "ahmednagar", "aurangabad", "jalgaon", "kolhapur", "mumbai", "mumbai-suburban",
        "nagpur", "nashik", "navi-mumbai", "pune", "solapur", "imphal", "shillong", "aizawl",
        "dimapur", "bhubaneswar", "cuttack", "paradeep", "puri", "rourkela", "amritsar", "bathinda",
        "jalandhar", "ludhiana", "mohali", "pathankot", "patiala", "ajmer", "jaipur", "jaisalmer",
        "jodhpur", "kota", "udaipur", "gangtok", "malegaon", "yeola", "sakri", "solhapur",
        "phulambari", "ashti", "karjat", "chennai", "coimbatore", "cuddalore", "erode", "hosur",
        "madurai", "nagercoil", "ooty", "salem", "thanjavur", "tirunelveli", "tiruchirapalli",
        "thoothukudi", "vellore", "agartala", "dadra-nagar-haveli", "daman-diu", "puducherry",
        "agra", "aligarh", "prayagraj", "bareilly", "ayodhya", "ghaziabad", "gorakhpur", "kanpur",
        "lucknow", "mathura", "meerut", "moradabad", "sinar", "dhule", "yavatmal", "katni", "patan",
        "ratlam", "location", "chhapra", "kalaburagi", "chembur", "noida", "varanasi", "dehradun",
        "roorkee", "asansol", "kailash", "janankpuri", "daspur", "durgapur", "haldia", "kharagpur",
        "kolkata", "siliguri", "alleppey", "baddi", "bhilwara", "idukki", "kasargode", "lakshadweep",
        "malappuram", "pathanamthitta", "port-blair", "port blair", "raigarh", "wayanad",
        "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh", "rewari", "burdwan",
        "bolpur", "begusarai", "prabhadevi", "goregaon", "goa", "gujarat", "haryana",
        "himachal pradesh", "chinchwad", "trivandrum", "calicut", "midnapore", "bhubaneshwar",
        "baroda", "satana", "deola", "jharkhand", "karnataka", "kerala", "madhya pradesh",
        "maharashtra", "manipur", "meghalaya", "mizoram", "nagaland", "odisha", "punjab",
        "rajasthan", "sikkim", "tamil nadu", "telangana", "tripura", "uttar pradesh", "uttarakhand",
        "muzaffarnagar", "bapunagar", "tirupur", "motihari", "punawale", "west bengal",
        "andaman and nicobar", "chandigarh", "janakpuri", "dadra and nagar haveli",
        "daman and diu", "puducherry"
    ]

    KEYWORDS = [
        "manager", "mgr", "am", "developer", "dev", "sde", "engineer", "engg", "engr", "analyst",
        "consultant", "lead", "head", "architect", "doctor", "coder", "director", "cto", "ceo",
        "coo", "vp", "president", "executive", "officer", "supervisor", "intern", "internship",
        "specialist", "associate", "administrator", "designer", "tester", "qa", "technician",
        "marketer", "evaluator", "crafter", "configurator", "instructor", "receptionist", "scientist",
        "trainer", "coordinator", "co-ordinator", "strategist", "principal", "owner", "founder",
        "staff", "underwriter", "chemist", "in-charge", "product", "project", "program", "team lead",
        "advisor", "assistant", "trainee", "reporter", "operators", "agents", "pilot", "agm", "gm",
        "chartered accountant", "accountant", "teacher", "tutor", "buyer", "surveyor", "counselor",
        "counsellor", "guard", "editor", "hr generalist", "expert", "professional", "writer",
        "analysts", "journalists", "artist", "contractor", "barista", "consultants", "investigator",
        "volunteer", "operator", "draftsman", "draftman", "draftsmen", "technologist", "executives",
        "engineers", "chancellor", "clerk", "asst.", "agronomist", "librarian", "attender",
        "trainees", "managers", "physician", "nephrologist", "gastroenterologist", "writers",
        "salesmen", "nurses", "technicians", "radiographer", "invesigator", "welder", "supervisors",
        "counsellors", "trainers", "experts", "advisors", "stenographer", "administrators",
        "designers", "surveyors", "animators", "freshers", "hacker", "representatives", "editors",
        "accountants", "officers", "teachers", "leaders", "videographer", "professionals",
        "beautician", "attenders", "gynaecologist", "nutritionist", "pathologist", "phlebotomist",
        "dietician", "doctors", "pgt", "tgt", "prt", "teamlead", "associates", "telecallers",
        "guide", "histopathologist", "microbiologist", "conceptualiser", "generalist",
        "representative", "faculty", "programmers", "recruiter", "vaccinator", "proof-reader",
        "proofreader", "content creator", "electrician", "controller", "business partner", "partner",
        "chef", "translator", "planner", "plannar", "culinarian", "moderator", "modeler", "plumber",
        "avp", "programmer", "commi", "leader", "developers", "recruiters", "resident", "registrar",
        "modeller", "sdet", "agent", "rm", "cashier", "scrum master", "counsel", "validator",
        "superintendent", "fellow", "apprentice", "architects", "draughtsman", "asstmgr",
        "bartender", "physiotherapist", "admin", "correspondent", "producer", "sme", "researcher",
        "visualizer", "visualiser", "scientists", "captains", "cook", "storekeeper", "ba", "bdm",
        "bde", "copywriter", "pharmacist", "inspector", "optometrist", "conceptualizer", "teller",
        "auditor", "trader", "lawyer", "telecaller", "ca", "fresher", "psychologist", "practitioner",
        "intensivist", "radiologist", "cardiologist", "professor", "educator", "caller", "captain",
        "neurologist", "freelancer", "crew", "stewards", "steward", "store keeper", "incharge",
        "office boy", "nurse", "secretary", "coders", "hrbp", "biochemist", "journalist", "foreman",
        "coach", "chief", "animator", "attendant", "commis", "junior", "helper", "surgeon", "dealer",
        "therapist"
    ]

    @staticmethod
    def validate_job_title(title: str) -> str:
        """
        Validate a job title.

        Args:
            title: Job title to validate

        Returns:
            "Valid", or "Invalid (<reason>; <reason>)" listing every failed check
        """
        if not isinstance(title, str) or not title.strip():
            return "Invalid (Empty Title)"

        errors = []

        def add_error(new_err: str):
            if new_err not in errors:
                errors.append(new_err)

        # Normalise punctuation to spaces before the phrase/location/keyword
        # scans, so "Sr. Manager" and "Manager-Ops" still match their keywords.
        lower_title = title.strip().lower()
        for ch in ["_", ",", ".", "(", ")", "|", "/", "-"]:
            lower_title = lower_title.replace(ch, " ")
        while "  " in lower_title:
            lower_title = lower_title.replace("  ", " ")
        lower_title = lower_title.strip()

        if re.match(r"^[^a-zA-Z0-9]", title.strip()):
            add_error("Starts with Special Character")

        if len(title.strip()) >= 70:
            add_error("Too Long")

        for phrase in TitleValidator.BAD_PHRASES:
            if phrase in lower_title:
                add_error("Contains Hiring Phrase")
                break

        # Run against the ORIGINAL title: normalisation above turns "/" and "-"
        # into spaces, so a date would never still contain its separators by
        # the time this pattern sees it.
        #
        # A bare "3-5" is an experience range, not a date, and is caught by the
        # experience rule below - so require either a slash ("12/05") or a full
        # three-part value ("1-2-2025") before calling it a date.
        if re.search(r"\b\d{1,2}/\d{1,2}(/\d{2,4})?\b", title) or \
           re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", title):
            add_error("Contains Date")

        if re.search(r"\b\d+\s*\+?\s*(year|years|yr|yrs)\b", lower_title, re.IGNORECASE):
            add_error("Contains Experience")

        for sw in TitleValidator.SALARY_WORDS:
            if sw in lower_title:
                add_error("Contains Salary Info")
                break

        for loc in TitleValidator.LOCATIONS:
            pattern = r"\b" + re.escape(loc).replace(r"\-", r"[ -]") + r"\b"
            if re.search(pattern, lower_title, re.IGNORECASE):
                add_error("Contains Location")
                break

        if re.search(r"[?!@%]", title):
            add_error("Special Character Error")

        if re.search(r"[^a-zA-Z0-9)\}\]\s]\s*$", title):
            add_error("Ends with Special Character")

        if re.search(r"(\([^)]*$)|(\{[^}]*$)|(\[[^\]]*$)", title):
            add_error("Unclosed Bracket")

        has_keyword = False
        for kw in TitleValidator.KEYWORDS:
            safe_kw = re.escape(kw).replace(r"\ ", r"\s+").replace(r"\-", r"[ -]")
            if re.search(r"\b" + safe_kw + r"\b", lower_title, re.IGNORECASE):
                has_keyword = True
                break

        if not has_keyword:
            add_error("Not a Job Title")

        if errors:
            return "Invalid (" + "; ".join(errors) + ")"

        return "Valid"

    @staticmethod
    def validate(title: str) -> Tuple[bool, List[ValidationError]]:
        """
        ValidationError-shaped wrapper around validate_job_title.

        Returns:
            (is_valid, error_list) - the list holds one entry carrying the full
            "Invalid (...)" status so callers can log or store the reasons.
        """
        status = TitleValidator.validate_job_title(title)

        if status == "Valid":
            return True, []

        return False, [ValidationError("title", "INVALID_TITLE", status)]


class LocationValidator:
    """Validates job locations according to guidelines"""

    INDIAN_STATES = {
        "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
        "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
        "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
        "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
        "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal"
    }

    @staticmethod
    def validate(location: str) -> Tuple[bool, List[ValidationError]]:
        """
        Validate location - must be Indian city, not state

        Args:
            location: Location string

        Returns:
            (is_valid, error_list)
        """
        errors = []

        if not location or not isinstance(location, str):
            return False, [ValidationError("location", "EMPTY_LOCATION", "Location is empty")]

        location = location.strip().lower()

        # Check if it's a state (not allowed)
        if location in LocationValidator.INDIAN_STATES:
            errors.append(ValidationError(
                "location", "STATE_NOT_CITY",
                f"'{location}' is an Indian state, not a city. Use specific city name."
            ))
            return False, errors

        return len([e for e in errors if e.severity == "error"]) == 0, errors


class EducationValidator:
    """Validates and provides default education values"""

    # Default education values per guidelines
    DEFAULT_UG = "#9502:"  # Any UG
    DEFAULT_PG = "#9511:"  # Any PG

    @staticmethod
    def get_defaults() -> Dict[str, str]:
        """Get default education values"""
        return {
            "ug": EducationValidator.DEFAULT_UG,
            "pg": EducationValidator.DEFAULT_PG
        }

    @staticmethod
    def validate(ug: Optional[str], pg: Optional[str]) -> Tuple[bool, List[ValidationError]]:
        """
        Validate education fields

        Args:
            ug: Undergraduate value
            pg: Postgraduate value

        Returns:
            (is_valid, error_list)
        """
        errors = []

        # At least UG is required
        if not ug:
            errors.append(ValidationError(
                "education", "MISSING_UG",
                "Undergraduate education is required"
            ))

        if errors:
            return False, errors

        return True, []


class ExperienceValidator:
    """Validates experience range"""

    @staticmethod
    def validate(min_exp: Optional[str], max_exp: Optional[str]) -> Tuple[bool, List[ValidationError]]:
        """
        Validate experience range

        Args:
            min_exp: Minimum experience
            max_exp: Maximum experience

        Returns:
            (is_valid, error_list)
        """
        errors = []

        if not min_exp or not max_exp:
            errors.append(ValidationError(
                "experience", "MISSING_RANGE",
                "Experience must be in valid range format (e.g., 3-5 Years)"
            ))
            return False, errors

        try:
            min_val = int(str(min_exp).strip())
            max_val = int(str(max_exp).strip())

            if min_val < 0:
                errors.append(ValidationError(
                    "experience", "INVALID_MIN",
                    "Minimum experience cannot be negative"
                ))

            if max_val < min_val:
                errors.append(ValidationError(
                    "experience", "INVALID_RANGE",
                    f"Maximum experience ({max_val}) cannot be less than minimum ({min_val})"
                ))

        except ValueError:
            errors.append(ValidationError(
                "experience", "NOT_NUMERIC",
                "Experience values must be numeric"
            ))

        return len(errors) == 0, errors


class JobValidator:
    """Master validator combining all validators"""

    def __init__(self):
        self.title_validator = TitleValidator()
        self.location_validator = LocationValidator()
        self.education_validator = EducationValidator()
        self.experience_validator = ExperienceValidator()

    def validate_job(self, job_data: Dict) -> Tuple[bool, List[ValidationError]]:
        """
        Validate complete job data

        Args:
            job_data: Dictionary with job fields

        Returns:
            (is_valid, error_list)
        """
        all_errors = []

        # Validate title (mandatory)
        title = job_data.get('title')
        title_valid, title_errors = self.title_validator.validate(title)
        all_errors.extend(title_errors)

        # Validate location (mandatory)
        location = job_data.get('location')
        loc_valid, loc_errors = self.location_validator.validate(location)
        all_errors.extend(loc_errors)

        # Validate experience (mandatory)
        min_exp = job_data.get('min_experience')
        max_exp = job_data.get('max_experience')
        exp_valid, exp_errors = self.experience_validator.validate(min_exp, max_exp)
        all_errors.extend(exp_errors)

        # Validate education (can use defaults)
        ug = job_data.get('ug')
        pg = job_data.get('pg')
        edu_valid, edu_errors = self.education_validator.validate(ug, pg)
        all_errors.extend(edu_errors)

        # Separate errors from warnings
        critical_errors = [e for e in all_errors if e.severity == "error"]
        warnings = [e for e in all_errors if e.severity == "warning"]

        is_valid = len(critical_errors) == 0

        # Log warnings
        for warning in warnings:
            logger.warning(f"[{warning.field}] {warning.message}")

        # Log errors
        for error in critical_errors:
            logger.error(f"[{error.field}] {error.message}")

        return is_valid, all_errors

    def get_error_summary(self, errors: List[ValidationError]) -> Dict[str, List[str]]:
        """
        Get human-readable error summary for reporting

        Args:
            errors: List of validation errors

        Returns:
            Dictionary grouped by severity
        """
        summary = {
            'errors': [],
            'warnings': []
        }

        for error in errors:
            if error.severity == "error":
                summary['errors'].append(error.message)
            else:
                summary['warnings'].append(error.message)

        return summary
