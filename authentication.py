"""
Authentication and Cookie Management Module
Handles cookie fetching, validation, refresh, and error reporting
"""

import requests
import logging
import json
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import base64
import re

logger = logging.getLogger(__name__)


class CookieManager:
    """Manages authentication cookies with validation and refresh"""

    def __init__(self, api_endpoint: str, username: str = "automation", password: str = None):
        """
        Initialize cookie manager

        Args:
            api_endpoint: URL to fetch cookies from
            username: Username for authentication (default: 'automation')
            password: Password for authentication (optional)
        """
        self.api_endpoint = api_endpoint
        self.username = username
        self.password = password
        self.cookies = {}
        self.last_fetched = None
        self.cookie_expiry = None
        self.is_valid = False

    def fetch_cookies(self) -> Tuple[bool, str]:
        """
        Fetch cookies from API endpoint (GET request)

        Returns:
            (success, message)
        """
        try:
            logger.info(f"Fetching cookies from {self.api_endpoint}")

            # Use GET request (not POST) - this is what the API expects
            response = requests.get(
                self.api_endpoint,
                timeout=30,
                verify=False  # Ignore SSL certificate warnings for internal endpoints
            )

            logger.debug(f"API response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                logger.debug(f"API response: {data}")

                # Extract cookies from response
                # Expected format: {"content": [{"cookies": "inauk_at=xxx;inauk_rt=yyy;..."}]}
                try:
                    cookies_str = data.get('content', [{}])[0].get('cookies', '')

                    if cookies_str:
                        # Parse cookie string to dictionary
                        self.cookies = self._parse_cookie_string(cookies_str)
                        self.last_fetched = datetime.now()

                        logger.info(f"Cookies fetched successfully. Count: {len(self.cookies)}")
                        return True, "Cookies fetched successfully"
                    else:
                        logger.error("No cookies in response content")
                        return False, "No cookies found in API response"
                except (IndexError, KeyError) as e:
                    logger.error(f"Error parsing response structure: {str(e)}")
                    logger.debug(f"Full response data: {data}")
                    return False, f"Invalid response structure: {str(e)}"
            else:
                logger.error(f"API returned status {response.status_code}")
                logger.debug(f"Response text: {response.text[:500]}")
                error_text = response.text[:200] if response.text else "No response body"

                # Try to parse error message if JSON
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', error_text)
                    logger.error(f"API error message: {error_msg}")
                except:
                    error_msg = error_text

                return False, f"HTTP {response.status_code}: {error_msg}"

        except requests.Timeout:
            logger.error(f"Timeout fetching cookies from {self.api_endpoint}")
            return False, f"Timeout after 30 seconds"
        except requests.ConnectionError as e:
            logger.error(f"Connection error: {str(e)}")
            return False, f"Connection error: {str(e)}"
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {str(e)}")
            return False, f"Invalid JSON response from API"
        except Exception as e:
            logger.error(f"Error fetching cookies: {str(e)}")
            return False, f"Error: {str(e)[:100]}"

    def _parse_cookie_string(self, cookie_str: str) -> Dict[str, str]:
        """
        Parse cookie string to dictionary

        Args:
            cookie_str: Cookie string (e.g., "inauk_at=xxx; inauk_rt=yyy")

        Returns:
            Dictionary of cookies
        """
        cookies = {}
        try:
            for cookie in cookie_str.split(';'):
                if '=' in cookie:
                    key, value = cookie.strip().split('=', 1)
                    cookies[key.strip()] = value.strip()
        except Exception as e:
            logger.error(f"Error parsing cookie string: {str(e)}")

        return cookies

    def validate_cookies(self) -> Tuple[bool, Optional[str]]:
        """
        Validate cookies - check if they exist and are not stale

        Returns:
            (is_valid, error_message)
        """
        if not self.cookies:
            return False, "No cookies available"

        # Check required cookies
        required_cookies = ['inauk_at', 'inauk_rt']
        missing = [c for c in required_cookies if c not in self.cookies]

        if missing:
            return False, f"Missing cookies: {', '.join(missing)}"

        # Check if token is expired (basic JWT check)
        try:
            inauk_at = self.cookies.get('inauk_at', '')
            if inauk_at and len(inauk_at) > 50:  # Looks like a JWT
                expiry_status, error = self._check_jwt_expiry(inauk_at)
                if not expiry_status:
                    logger.warning(f"Token validation warning: {error}")
                    # Still consider valid but warn
                    return True, None
        except Exception as e:
            logger.warning(f"Could not validate JWT: {str(e)}")

        self.is_valid = True
        return True, None

    def _check_jwt_expiry(self, token: str) -> Tuple[bool, Optional[str]]:
        """
        Check JWT token expiry

        Args:
            token: JWT token

        Returns:
            (is_valid, error_message)
        """
        try:
            parts = token.split('.')
            if len(parts) < 2:
                return True, None  # Not a valid JWT, skip check

            # Decode payload
            payload = parts[1]
            # Add padding
            padding = 4 - (len(payload) % 4)
            if padding != 4:
                payload += '=' * padding

            decoded = base64.urlsafe_b64decode(payload)
            data = json.loads(decoded)

            if 'exp' in data:
                expiry_time = datetime.fromtimestamp(data['exp'])
                current_time = datetime.now()

                if expiry_time <= current_time:
                    return False, f"Token expired at {expiry_time}"

                # Warn if expiring soon
                time_left = (expiry_time - current_time).total_seconds() / 3600
                if time_left < 1:
                    return True, f"Token expires in {time_left:.1f} hours - consider refreshing"

                logger.info(f"Token valid, expires in {time_left:.1f} hours")
                return True, None

        except Exception as e:
            logger.debug(f"Could not decode JWT: {str(e)}")

        return True, None

    def refresh_cookies(self) -> Tuple[bool, str]:
        """
        Refresh cookies by fetching new ones

        Returns:
            (success, message)
        """
        logger.info("Attempting to refresh cookies...")
        return self.fetch_cookies()

    def get_cookies(self) -> Dict[str, str]:
        """Get current cookies"""
        return self.cookies.copy()

    def get_cookie_status(self) -> Dict[str, any]:
        """Get detailed cookie status"""
        is_valid, error = self.validate_cookies()

        return {
            'has_cookies': bool(self.cookies),
            'is_valid': is_valid,
            'error': error,
            'cookie_count': len(self.cookies),
            'last_fetched': self.last_fetched.isoformat() if self.last_fetched else None,
            'cookie_keys': list(self.cookies.keys()),
            'expiry': self.cookie_expiry
        }

    def ensure_valid_cookies(self) -> Tuple[bool, str]:
        """
        Ensure cookies are valid, refresh if needed

        Returns:
            (success, message)
        """
        is_valid, error = self.validate_cookies()

        if is_valid:
            logger.info("Cookies are valid")
            return True, "Cookies are valid"

        logger.warning(f"Cookies invalid: {error}. Attempting refresh...")
        success, message = self.refresh_cookies()

        if success:
            is_valid, error = self.validate_cookies()
            if is_valid:
                return True, "Cookies refreshed and valid"
            else:
                return False, f"Cookies refreshed but still invalid: {error}"

        return False, f"Failed to refresh cookies: {message}"


class AuthenticationError(Exception):
    """Custom exception for authentication errors"""
    pass


class CookieValidationError(AuthenticationError):
    """Exception for cookie validation failures"""

    def __init__(self, message: str, error_code: str = "COOKIE_INVALID"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class CookieExpiredError(AuthenticationError):
    """Exception for expired cookies"""

    def __init__(self, message: str = "Cookies have expired"):
        self.message = message
        self.error_code = "COOKIE_EXPIRED"
        super().__init__(self.message)
