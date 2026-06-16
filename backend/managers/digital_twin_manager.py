"""Digital twin manager: orchestrates digital twin grouping and loading."""

from .base_manager import BaseManager
from .dataset_manager import DatasetManager
from ..api.digital_twins_client import DigitalTwinsClient
from ..managers.errors import APIError


class DigitalTwinManager(BaseManager):
    """Manages digital twin operations.

    Digital twins are logical groupings of datasets by owner hub.
    This manager handles:
    - Grouping datasets into digital twin structures
    - Loading all datasets in a digital twin
    """

    def __init__(self, dataset_manager=None,
                 auth_context=None, cache_ttl=None):
        """Initialize digital twin manager.

        Args:
            dataset_manager: Optional DatasetManager instance (or creates new one).
            auth_context: Optional auth context.
            cache_ttl: Optional cache TTL override.
        """
        super().__init__(cache_ttl=cache_ttl)
        self.auth_context = auth_context
        self.dataset_manager = dataset_manager or DatasetManager(
            auth_context=auth_context)
        self.client = DigitalTwinsClient()

    def _get_user_token(self):
        if not self.auth_context:
            return None
        return getattr(self.auth_context, "_get_user_token", lambda: None)()

    def _is_authenticated(self):
        if not self.auth_context:
            return False
        return getattr(self.auth_context, "is_authenticated", lambda: False)()

    def _extract_results_payload(self, data):
        if isinstance(data, list):
            return data, len(data)
        if isinstance(data, dict):
            results = data.get("results") or data.get("items") or []
            count = data.get("count")
            if not isinstance(count, int):
                count = data.get("total")
            return results, count
        return [], 0

    def _valid_preview_url(self, value):
        text = str(value or "").strip()
        if not text:
            return ""
        lowered = text.lower()
        if not (lowered.startswith("http://")
                or lowered.startswith("https://")):
            return ""
        if "/null" in lowered or lowered.endswith("/public/"):
            return ""
        return text

    def _extract_twin_preview_url(self, twin):
        for key in ("previewImage", "landscapePreviewImage",
                    "previewInfoImage"):
            url = self._valid_preview_url(twin.get(key))
            if url:
                return url

        owner_hub = twin.get("ownerHub") or {}
        participants = owner_hub.get(
            "participants") if isinstance(owner_hub, dict) else []
        for participant in participants or []:
            if not isinstance(participant, dict):
                continue
            url = self._valid_preview_url(participant.get("profilePictureUrl"))
            if url:
                return url
        return ""

    def _dataset_stats_by_owner_hub(self, datasets):
        stats = {}
        for dset in datasets or []:
            hub_name = str(
                dset.get("owner_hub") or dset.get("hub") or "").strip()
            if not hub_name:
                continue
            if hub_name not in stats:
                stats[hub_name] = {"datasets_count": 0, "formats": set()}
            stats[hub_name]["datasets_count"] += 1
            for fmt in dset.get("formats") or []:
                stats[hub_name]["formats"].add(str(fmt))
        return stats

    def _build_twin_info(self, twin, dataset_stats):
        owner_hub = twin.get("ownerHub") or {}
        owner_hub_name = str(
            owner_hub.get("name") or "Unknown Hub").strip() or "Unknown Hub"
        parent = owner_hub.get("parent") if isinstance(
            owner_hub, dict) else None
        parent_name = str((parent or {}).get("name") or "").strip()
        stats = dataset_stats.get(
            owner_hub_name, {
                "datasets_count": 0, "formats": set()})

        findability = str(twin.get("findability") or "").upper()
        findability_values = [findability] if findability else ["UNKNOWN"]

        return {
            "id": twin.get("_id") or twin.get("id") or owner_hub_name,
            "title": twin.get("title") or "No Title",
            "description": twin.get("description") or "No Description",
            "owner_hub": owner_hub_name,
            "owner_hub_id": owner_hub.get("_id") if isinstance(owner_hub, dict) else "",
            "part_of_hub": parent_name,
            "part_of_hubs": [parent_name] if parent_name else [],
            "findability": ", ".join(findability_values),
            "findability_values": findability_values,
            "datasets_count": stats["datasets_count"],
            "formats": ", ".join(sorted(stats["formats"])) if stats["formats"] else "unknown",
            "profile_picture_url": self._extract_twin_preview_url(twin),
        }

    def get_all_digital_twins(self, datasets=None):
        """Fetch digital twins and normalize to frontend card schema.

        Args:
            datasets: Optional pre-fetched normalized datasets used to compute
                owner hub stats. When omitted, datasets are fetched internally.

        Returns:
            List of digital twin dicts.
        """
        try:
            token = self._get_user_token() if self._is_authenticated() else None
            rows = []
            offset = 0
            page_size = 200
            total_count = None

            while True:
                data = self.client.get_digital_twins(
                    limit=page_size,
                    offset=offset,
                    user_token=token,
                ) or {}
                page_rows, total = self._extract_results_payload(data)
                if total_count is None and isinstance(total, int):
                    total_count = total
                if not page_rows:
                    break

                rows.extend(page_rows)
                offset += len(page_rows)

                if total_count is not None and len(rows) >= total_count:
                    break
                if page_size and len(page_rows) < page_size:
                    break

            datasets_for_stats = datasets if datasets is not None else self.dataset_manager.get_all_datasets()
            dataset_stats = self._dataset_stats_by_owner_hub(
                datasets_for_stats)
            twins = [
                self._build_twin_info(
                    twin,
                    dataset_stats) for twin in rows]
            twins.sort(key=lambda x: (x.get("title") or "").lower())
            return twins
        except APIError as e:
            self._log(f"Failed to get digital twins: {str(e)}", "warning")
            return []

    def load_digital_twin(self, digital_twin_id, load_layer_func):
        """Load all datasets in a digital twin.

        Args:
            digital_twin_id: Digital twin ID (typically hub name).
            load_layer_func: Callable that loads a single layer by dataset_id.
                Expected signature: load_layer_func(dataset_id) -> Layer or None

        Returns:
            Summary dict with "total", "loaded", "failed", "failed_ids".
        """
        try:
            datasets = self.dataset_manager.get_all_datasets()
        except APIError as e:
            self._log(
                f"Failed to fetch datasets for twin {digital_twin_id}: {
                    str(e)}", "warning")
            return {"total": 0, "loaded": 0, "failed": 0, "failed_ids": []}

        owner_hub_name = str(digital_twin_id or "").strip()
        try:
            twin_rows = self.get_all_digital_twins()
            twin_match = next(
                (tw for tw in twin_rows if str(
                    tw.get("id") or "").strip() == owner_hub_name),
                None,
            )
            if twin_match:
                owner_hub_name = str(
                    twin_match.get("owner_hub") or owner_hub_name).strip()
        except Exception:
            pass

        # Find datasets belonging to this twin's owner hub.
        dataset_ids = [
            ds["id"] for ds in datasets
            if str(ds.get("owner_hub") or ds.get("hub") or "").strip() == owner_hub_name
        ]
        if not dataset_ids:
            return {"total": 0, "loaded": 0, "failed": 0, "failed_ids": []}

        loaded = 0
        failed_ids = []

        for ds_id in dataset_ids:
            try:
                result = load_layer_func(ds_id)
                if result is None:
                    failed_ids.append(ds_id)
                else:
                    loaded += 1
            except Exception as e:
                self._log(
                    f"Failed to load dataset {ds_id}: {
                        str(e)}", "WARNING")
                failed_ids.append(ds_id)

        return {
            "total": len(dataset_ids),
            "loaded": loaded,
            "failed": len(failed_ids),
            "failed_ids": failed_ids,
        }
