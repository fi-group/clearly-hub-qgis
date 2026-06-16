"""Hubs API client."""

from .client import Client


class HubsClient(Client):
    """HTTP client for hubs endpoints."""

    def get_hubs(self, user_token=None):
        """Fetch all hubs from API.

        Args:
            user_token: Optional auth token for private hubs.

        Returns:
            Paginated response {"count": ..., "results": [...]}.
        """
        return self.get("/hubs", user_token=user_token)

    def get_hub_by_id(self, hub_id, user_token=None):
        """Fetch a single hub by ID.

        Args:
            hub_id: Hub ID.
            user_token: Optional auth token.

        Returns:
            Hub dict.
        """
        return self.get(f"/hubs/{hub_id}", user_token=user_token)
