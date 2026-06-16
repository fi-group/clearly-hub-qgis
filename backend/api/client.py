"""Base HTTP client with retry logic, headers, and error handling."""

import requests
from ..managers.errors import APIError


class Client:
    """Base HTTP client for API communication.

    Handles headers, authentication, timeouts, and error responses.
    """

    BASE_URL = "https://hub.clearly.app/api"
    TIMEOUT = 15

    def __init__(self, base_url=None, timeout=None):
        """Initialize client with optional base URL and timeout override.

        Args:
            base_url: Optional API base URL.
            timeout: Optional request timeout in seconds.
        """
        self.base_url = base_url or self.BASE_URL
        self.timeout = timeout or self.TIMEOUT

    def _headers(self, user_token=None):
        """Build request headers with optional auth.

        Args:
            user_token: Optional OAuth access token.

        Returns:
            Dict of headers.
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "clearlyhub-qgis-plugin/1.0"
        }
        if user_token:
            headers["Authorization"] = f"Bearer {user_token}"
        return headers

    def get(self, endpoint, params=None, user_token=None):
        """Perform a GET request.

        Args:
            endpoint: API endpoint path (e.g., "/datasets").
            params: Optional query parameters dict.
            user_token: Optional auth token.

        Returns:
            Parsed JSON response dict.

        Raises:
            APIError if request fails.
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(
                url,
                params=params,
                headers=self._headers(user_token),
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise APIError(f"GET {endpoint} failed: {str(e)}") from e

    def post(self, endpoint, data=None, user_token=None):
        """Perform a POST request.

        Args:
            endpoint: API endpoint path.
            data: Optional JSON body dict.
            user_token: Optional auth token.

        Returns:
            Parsed JSON response dict.

        Raises:
            APIError if request fails.
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.post(
                url,
                json=data,
                headers=self._headers(user_token),
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise APIError(f"POST {endpoint} failed: {str(e)}") from e
