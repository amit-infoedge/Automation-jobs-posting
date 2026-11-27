"""
Utility Functions for Job Posting Automation
"""

import logging
import json
import re
from typing import Dict, Any, List, Optional
import pandas as pd
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DataCleaner:
    """Utilities for data cleaning and transformation"""

    @staticmethod
    def clean_string(value: Any, strip: bool = True, lowercase: bool = False) -> str:
        """
        Clean string values

        Args:
            value: Value to clean
            strip: Whether to strip whitespace
            lowercase: Whether to convert to lowercase

        Returns:
            Cleaned string
        """
        if value is None:
            return ""

        result = str(value).strip() if strip else str(value)
        if lowercase:
            result = result.lower()

        return result

    @staticmethod
    def clean_numeric(value: Any, default: float = 0.0) -> float:
        """
        Clean numeric values

        Args:
            value: Value to clean
            default: Default value if invalid

        Returns:
            Cleaned numeric value
        """
        try:
            if value is None or str(value).strip() == "":
                return default
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Cannot convert '{value}' to float, using default {default}")
            return default

    @staticmethod
    def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean entire DataFrame

        Args:
            df: DataFrame to clean

        Returns:
            Cleaned DataFrame
        """
        try:
            # Remove completely empty rows
            df = df.dropna(how='all')

            # Replace NaN with empty strings for string columns
            string_columns = df.select_dtypes(include=['object']).columns
            for col in string_columns:
                df[col] = df[col].fillna("").astype(str)

            # Strip whitespace from string columns
            for col in string_columns:
                df[col] = df[col].str.strip()

            logger.info(f"Cleaned DataFrame: {df.shape[0]} rows, {df.shape[1]} columns")
            return df
        except Exception as e:
            logger.error(f"Error cleaning DataFrame: {str(e)}")
            return df

    @staticmethod
    def handle_encoding(text: str) -> str:
        """
        Handle special character encoding (e.g., non-breaking spaces)

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Replace non-breaking space (character 160) with regular space
        return text.replace(chr(160), " ")


class ResponseParser:
    """Parse API responses"""

    @staticmethod
    def extract_job_id(redirect_url: str) -> Optional[str]:
        """
        Extract job ID from redirect URL

        Args:
            redirect_url: URL returned after job posting

        Returns:
            Job ID or None
        """
        try:
            match = re.search(r'(\d{12})', redirect_url)
            if match:
                return match.group(1)
        except Exception as e:
            logger.error(f"Error extracting job ID: {str(e)}")

        return None

    @staticmethod
    def parse_error_response(response_text: str) -> List[str]:
        """
        Parse error messages from HTML response

        Args:
            response_text: HTML response

        Returns:
            List of error messages
        """
        errors = []

        try:
            # Extract error divs
            error_matches = re.findall(r'class="error"[^>]*>([^<]+)<', response_text)
            errors.extend(error_matches)

            # Extract error messages from JSON if embedded
            json_matches = re.findall(r'"error"[^:]*:\s*"([^"]+)"', response_text)
            errors.extend(json_matches)

        except Exception as e:
            logger.error(f"Error parsing error response: {str(e)}")

        return list(set(errors))  # Remove duplicates

    @staticmethod
    def extract_cookies_from_headers(headers: Dict[str, str]) -> Dict[str, str]:
        """
        Extract cookies from response headers

        Args:
            headers: Response headers

        Returns:
            Dictionary of cookies
        """
        cookies = {}

        try:
            set_cookie = headers.get('Set-Cookie', '')
            if set_cookie:
                parts = set_cookie.split(';')
                cookie_pair = parts[0].split('=')
                if len(cookie_pair) == 2:
                    cookies[cookie_pair[0].strip()] = cookie_pair[1].strip()

        except Exception as e:
            logger.error(f"Error extracting cookies: {str(e)}")

        return cookies


class FileManager:
    """Manage file operations"""

    @staticmethod
    def save_csv(data: List[Dict[str, Any]], filepath: str) -> bool:
        """
        Save data to CSV file

        Args:
            data: List of dictionaries
            filepath: Output file path

        Returns:
            True if successful
        """
        try:
            df = pd.DataFrame(data)
            df.to_csv(filepath, index=False)
            logger.info(f"Saved {len(data)} records to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving CSV: {str(e)}")
            return False

    @staticmethod
    def save_json(data: Dict[str, Any], filepath: str) -> bool:
        """
        Save data to JSON file

        Args:
            data: Dictionary to save
            filepath: Output file path

        Returns:
            True if successful
        """
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            logger.info(f"Saved data to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving JSON: {str(e)}")
            return False

    @staticmethod
    def load_json(filepath: str) -> Optional[Dict[str, Any]]:
        """
        Load data from JSON file

        Args:
            filepath: File path

        Returns:
            Dictionary or None
        """
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading JSON: {str(e)}")
            return None


class TimeUtils:
    """Time and date utilities"""

    @staticmethod
    def get_current_timestamp() -> str:
        """Get current timestamp in standard format"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def get_file_timestamp() -> str:
        """Get timestamp suitable for filenames"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    @staticmethod
    def is_past_date(date_str: str, format: str = "%Y-%m-%d") -> bool:
        """
        Check if date is in the past

        Args:
            date_str: Date string
            format: Date format

        Returns:
            True if date is in past
        """
        try:
            date = datetime.strptime(date_str, format)
            return date < datetime.now()
        except Exception as e:
            logger.error(f"Error checking date: {str(e)}")
            return False

    @staticmethod
    def days_since(date_str: str, format: str = "%Y-%m-%d") -> int:
        """
        Calculate days since a date

        Args:
            date_str: Date string
            format: Date format

        Returns:
            Number of days
        """
        try:
            date = datetime.strptime(date_str, format)
            delta = datetime.now() - date
            return delta.days
        except Exception as e:
            logger.error(f"Error calculating days: {str(e)}")
            return 0


class ValidationUtils:
    """Validation utilities"""

    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Validate email address"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Validate URL"""
        pattern = r'https?://[^\s/$.?#].[^\s]*'
        return bool(re.match(pattern, url, re.IGNORECASE))

    @staticmethod
    def is_valid_job_id(job_id: str) -> bool:
        """Validate job ID format (should be 12 digits)"""
        return bool(re.match(r'^\d{12}$', str(job_id)))

    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> List[str]:
        """
        Validate that required fields are present and not empty

        Args:
            data: Data dictionary
            required_fields: List of required field names

        Returns:
            List of missing fields
        """
        missing = []

        for field in required_fields:
            value = data.get(field)
            if not value or (isinstance(value, str) and value.strip() == ""):
                missing.append(field)

        return missing
