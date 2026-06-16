"""Hub manager: orchestrates hub fetching and normalization."""

from .base_manager import BaseManager
from ..api.hubs_client import HubsClient
from ..managers.errors import APIError


class HubManager(BaseManager):
    """Manages hub fetching and normalization.

    Responsibilities:
    - Coordinate API calls to fetch hubs
    - Apply auth-based filtering if needed
    - Cache results for performance
    """

    def __init__(self, auth_context=None, cache_ttl=None):
        """Initialize hub manager.

        Args:
            auth_context: Optional auth context.
            cache_ttl: Optional cache TTL override.
        """
        super().__init__(cache_ttl=cache_ttl)
        self.auth_context = auth_context
        self.client = HubsClient()

    def _get_user_token(self):
        """Get user token from auth context if available.

        Returns:
            User token string or None.
        """
        if not self.auth_context:
            return None
        return getattr(self.auth_context, '_get_user_token', lambda: None)()

    def _is_authenticated(self):
        """Check if user is authenticated.

        Returns:
            True if authenticated, False otherwise.
        """
        if not self.auth_context:
            return False
        return getattr(self.auth_context, 'is_authenticated', lambda: False)()

    def get_all_hubs(self):
        """Fetch all hubs.

        Results are cached.

        Returns:
            List of hub dicts.
        """
        try:
            token = self._get_user_token() if self._is_authenticated() else None
            response = self.client.get_hubs(user_token=token)
            if response is None:
                return []

            if isinstance(response, list):
                return response

            if isinstance(response, dict):
                return response.get("results", [])

            return []
        except APIError as e:
            self._log(f"Failed to fetch hubs: {str(e)}", "warning")
            return []

    def get_hub_by_id(self, hub_id):
        """Fetch a single hub by ID.

        Args:
            hub_id: Hub ID.

        Returns:
            Hub dict or None if not found.
        """
        if not hub_id:
            return None

        try:
            token = self._get_user_token() if self._is_authenticated() else None
            return self.client.get_hub_by_id(hub_id, user_token=token)
        except APIError as e:
            self._log(f"Failed to fetch hub {hub_id}: {str(e)}", "warning")
            return None
