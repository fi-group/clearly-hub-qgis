"""Dataset manager: orchestrates API calls and data normalization."""

from .base_manager import BaseManager
from ..api.datasets_client import DatasetsClient
from ..formatters.dataset_formatter import build_dataset_info
from ..managers.errors import APIError


class DatasetManager(BaseManager):
    """Manages dataset fetching, filtering, and normalization.
    
    Responsibilities:
    - Coordinate API calls to fetch datasets
    - Apply auth-based filtering (public vs private)
    - Normalize raw API responses into standardized format
    - Cache results for performance
    """
    
    def __init__(self, auth_context=None, cache_ttl=None):
        """Initialize dataset manager.
        
        Args:
            auth_context: Optional auth context with is_authenticated() and _get_user_token().
            cache_ttl: Optional cache TTL override.
        """
        super().__init__(cache_ttl=cache_ttl)
        self.auth_context = auth_context
        self.client = DatasetsClient()
    
    def _get_user_token(self):
        """Get user token from auth context if available.
        
        Returns:
            User token string or None.
        """
        if not self.auth_context:
            return None
        return getattr(self.auth_context, '_get_user_token', lambda: None)()
    
    def _is_authenticated(self):
        """Check if user is authenticated via auth context.
        
        Returns:
            True if authenticated, False otherwise.
        """
        if not self.auth_context:
            return False
        return getattr(self.auth_context, 'is_authenticated', lambda: False)()
    
    def _extract_datasets_payload(self, data):
        """Extract datasets and count from various API response structures.
        
        Args:
            data: Raw API response (list or dict).
        
        Returns:
            Tuple of (datasets_list, count_int).
        """
        if isinstance(data, list):
            return data, len(data)
        
        if isinstance(data, dict):
            results = data.get("results") or data.get("datasets") or data.get("items") or []
            count = data.get("count")
            if not isinstance(count, int):
                count = data.get("total")
            if not isinstance(count, int):
                count = data.get("totalCount")
            return results, count
        
        return [], 0
    
    def get_all_datasets(self, page_size=200):
        """Fetch all datasets by pagination.
        
        Automatically filters for public datasets if not authenticated.
        Results are cached.
        
        Args:
            page_size: Results per page (max per request).
        
        Returns:
            List of normalized dataset dicts.
        """
        token = self._get_user_token() if self._is_authenticated() else None
        all_rows = []
        
        try:
            offset = 0
            total_count = None
            while True:
                data = self.client.get_datasets(
                    limit=page_size,
                    offset=offset,
                    user_token=token,
                ) or {}
                rows, total = self._extract_datasets_payload(data)

                if total_count is None and isinstance(total, int):
                    total_count = total

                if not rows:
                    break

                all_rows.extend(rows)
                offset += len(rows)

                if total_count is not None and len(all_rows) >= total_count:
                    break

                # Safety stop when API does not provide total and returns a short page.
                if page_size and len(rows) < page_size:
                    break
        except APIError as e:
            # Log error but don't crash, returns empty list
            self._log(f"Failed to fetch all datasets: {str(e)}", "warning")
            all_rows = []
        
        # Normalize and filter
        normalized = [build_dataset_info(d) for d in all_rows]
        
        if not self._is_authenticated():
            normalized = [d for d in normalized if str(d.get("findability") or "").upper() == "PUBLIC"]
        
        return normalized
    
    def get_datasets_page(self, limit=None, offset=0):
        """Fetch a single page of datasets.
        
        Args:
            limit: Page size (optional).
            offset: Pagination offset.
        
        Returns:
            Dict with "count" and "results" keys.
        """
        token = self._get_user_token() if self._is_authenticated() else None
        
        try:
            data = self.client.get_datasets(limit=limit, offset=offset, user_token=token) or {}
        except APIError as e:
            self._log(f"Failed to fetch datasets page: {str(e)}", "warning")
            return {"count": 0, "results": []}
        
        raw_results, raw_count = self._extract_datasets_payload(data)
        
        # Normalize
        if self._is_authenticated():
            normalized = [build_dataset_info(d) for d in raw_results]
        else:
            normalized = [
                build_dataset_info(d) for d in raw_results
                if str(d.get("findability") or "").upper() == "PUBLIC"
            ]
        
        count = raw_count if isinstance(raw_count, int) else len(normalized)
        return {"count": count, "results": normalized}
    
    def get_dataset_by_id(self, dataset_id):
        """Fetch and normalize a single dataset by ID.
        
        Args:
            dataset_id: Dataset ID.
        
        Returns:
            Normalized dataset dict or None if not found.
        """
        if not dataset_id:
            return None
        
        try:
            data = self.client.get_dataset_by_id(dataset_id, user_token=self._get_user_token())
        except APIError as e:
            self._log(f"Failed to fetch dataset {dataset_id}: {str(e)}", "warning")
            return None
        
        if not data:
            return None
        
        return build_dataset_info(data)
    
    def get_public_datasets(self, limit=None, offset=0):
        """Fetch only public datasets (regardless of auth state).
        
        Args:
            limit: Page size (optional).
            offset: Pagination offset.
        
        Returns:
            List of public normalized dataset dicts.
        """
        try:
            data = self.client.get_datasets(limit=limit, offset=offset, user_token=None) or {}
        except APIError as e:
            self._log(f"Failed to fetch public datasets: {str(e)}", "warning")
            return []
        
        results = data.get("results", [])
        return [
            build_dataset_info(d) for d in results
            if str(d.get("findability") or "").upper() == "PUBLIC"
        ]
