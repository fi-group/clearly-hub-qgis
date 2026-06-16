"""Datasets API client."""

from .client import Client


class DatasetsClient(Client):
    """HTTP client for datasets endpoints."""

    def get_datasets(self, dataset_id=None, limit=None,
                     offset=0, user_token=None):
        """Fetch datasets from API.

        Args:
            dataset_id: Optional single dataset ID to fetch.
            limit: Optional max results per page.
            offset: Optional pagination offset.
            user_token: Optional auth token for private datasets.

        Returns:
            Single dataset dict or paginated response {"count": ..., "results": [...]}.
        """
        if dataset_id:
            return self.get(f"/datasets/{dataset_id}", user_token=user_token)

        params = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        return self.get("/datasets", params=params or None,
                        user_token=user_token)

    def get_dataset_by_id(self, dataset_id, user_token=None):
        """Fetch a single dataset by ID.

        Args:
            dataset_id: Dataset ID.
            user_token: Optional auth token.

        Returns:
            Dataset dict.
        """
        return self.get(f"/datasets/{dataset_id}", user_token=user_token)
