"""Digital twins API client."""

from .client import Client


class DigitalTwinsClient(Client):
    """HTTP client for digital twins endpoints."""

    def get_digital_twins(self, limit=None, offset=0, user_token=None):
        """Fetch digital twins from API.

        Args:
            limit: Optional max results per page.
            offset: Optional pagination offset.
            user_token: Optional auth token for private twins.

        Returns:
            Paginated response {"count": ..., "results": [...]}.
        """
        params = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        return self.get("/digital-twins", params=params or None, user_token=user_token)
