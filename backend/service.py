# service.py - Refactored to use managers
"""Service layer: high-level orchestration using managers for data operations.

This is now a thin controller that coordinates managers and handles auth state.
"""

from __future__ import annotations
from qgis.core import QgsProject

from .auth import AuthManager
from .managers.dataset_manager import DatasetManager
from .managers.hub_manager import HubManager
from .managers.digital_twin_manager import DigitalTwinManager
from .api.auth_client import AuthClient
from .formatters.dataset_formatter import normalize_format
from .formatters.metadata_formatter import dataset_metadata_payload, apply_layer_metadata
from .core.url_helpers import validate_url, parse_wms_url, get_wms_layers, get_wfs_typenames
from .core.layer_loader import (
    load_vector_layer,
    load_wfs_layer,
    load_raster_layer,
    load_3d_layer,
    load_terrain_layer,
    load_bim_layer,
    load_tileset_layer,
    load_point_cloud_layer,
)


class Service:
    """High-level service layer using managers for data operations.
    
    Responsibilities:
    - Manage authentication state
    - Coordinate managers for data fetching
    - Handle layer loading
    - Provide consistent API to UI
    """
    
    def __init__(self, authenticated_user=None):
        """Initialize service.
        
        Args:
            authenticated_user: Optional initial authenticated user.
        """
        self.auth_manager = AuthManager()
        self.current_user = authenticated_user
        
        # Initialize managers with auth context (self)
        self.dataset_manager = DatasetManager(auth_context=self)
        self.hub_manager = HubManager(auth_context=self)
        self.digital_twin_manager = DigitalTwinManager(
            dataset_manager=self.dataset_manager,
            auth_context=self
        )
        
        # Auth client for user info
        self.auth_client = AuthClient()

    # -------------------------------------------------------------------------
    # Auth helpers - provide context to managers
    # -------------------------------------------------------------------------
    
    def _get_user_token(self):
        """Get user token if authenticated.
        
        Returns:
            User token string or None.
        """
        return getattr(self.current_user, "token", None)

    def login(self):
        """Initiate login flow and update user info.
        
        Returns:
            AuthenticatedUser instance or None if login fails.
        """
        self.current_user = self.auth_client.get_authenticated_user(interactive=True)
        return self.current_user

    def logout(self):
        """Log out current user and clear auth state."""
        self.auth_manager.remove_authcfg()
        self.current_user = None

    def is_authenticated(self):
        """Check if user is currently authenticated.
        
        Returns:
            True if authenticated, False otherwise.
        """
        return self.current_user is not None or self.auth_manager.has_authcfg()

    def update_user_info(self):
        """Refresh user information from the API.
        
        Returns:
            Updated AuthenticatedUser instance or None.
        """
        self.current_user = self.auth_client.get_authenticated_user(interactive=False)
        return self.current_user

    # -------------------------------------------------------------------------
    # Dataset operations - delegated to DatasetManager
    # -------------------------------------------------------------------------
    
    def get_all_datasets(self, page_size=200):
        """Fetch all datasets (paginated internally).
        
        Automatically filters for public datasets if not authenticated.
        Results are cached by the manager.
        
        Args:
            page_size: Results per page (for pagination).
        
        Returns:
            List of normalized dataset dicts.
        """
        return self.dataset_manager.get_all_datasets(page_size=page_size)

    def get_datasets_page(self, limit=None, offset=0):
        """Fetch a single page of datasets.
        
        Args:
            limit: Page size (optional).
            offset: Pagination offset.
        
        Returns:
            Dict with "count" and "results" keys.
        """
        return self.dataset_manager.get_datasets_page(limit=limit, offset=offset)

    def get_datasets(self, limit=None, offset=0):
        """Get datasets page results only (convenience method).
        
        Args:
            limit: Page size (optional).
            offset: Pagination offset.
        
        Returns:
            List of dataset dicts.
        """
        page = self.get_datasets_page(limit=limit, offset=offset)
        return page.get("results", [])

    def get_public_datasets(self, limit=None, offset=0):
        """Fetch only public datasets regardless of auth state.
        
        Args:
            limit: Page size (optional).
            offset: Pagination offset.
        
        Returns:
            List of public dataset dicts.
        """
        return self.dataset_manager.get_public_datasets(limit=limit, offset=offset)

    # -------------------------------------------------------------------------
    # Hub operations - delegated to HubManager
    # -------------------------------------------------------------------------
    
    def get_hubs(self):
        """Fetch all hubs.
        
        Returns:
            List of hub dicts, or empty list if fetch fails.
        """
        hubs = self.hub_manager.get_all_hubs()
        if not hubs:
            return {"count": 0, "results": []}
        if isinstance(hubs, list):
            return {"count": len(hubs), "results": hubs}
        return hubs

    # -------------------------------------------------------------------------
    # Digital Twin operations - delegated to DigitalTwinManager
    # -------------------------------------------------------------------------
    
    def get_public_digital_twins(self, datasets=None):
        """Fetch and group all datasets into digital twins.
        
        Each digital twin represents a logical collection from one owner hub.
        Results are cached by the manager.

        Args:
            datasets: Optional pre-fetched normalized datasets used to compute
                digital twin stats without refetching datasets.
        
        Returns:
            List of digital twin dicts with aggregated metadata.
        """
        return self.digital_twin_manager.get_all_digital_twins(datasets=datasets)

    def load_digital_twin(self, digital_twin_id):
        """Load all datasets in a digital twin into QGIS.
        
        Args:
            digital_twin_id: Digital twin ID (typically owner hub name).
        
        Returns:
            Summary dict with "total", "loaded", "failed", "failed_ids".
        """
        return self.digital_twin_manager.load_digital_twin(
            digital_twin_id,
            load_layer_func=self.load_data
        )

    # -------------------------------------------------------------------------
    # Layer loading
    # -------------------------------------------------------------------------
    
    def load_data(self, dataset_id, resource_url=None, resource_format=None, resource_name=None, add_to_project=True):
        """Load a dataset into QGIS as a map layer.
        
        Fetches dataset info, validates URL, determines format, and creates
        appropriate QGIS layer type. Applies metadata and adds to project.
        
        Args:
            dataset_id: Dataset ID to load.
            resource_url: Optional override for resource URL.
            resource_format: Optional override for resource format.
            resource_name: Optional override for resource name.
            add_to_project: When False, prepare and return the layer without
                adding it to QgsProject (safe to call from a background thread).
        
        Returns:
            Created QgsMapLayer instance, or None if loading fails.
        """
        token = self._get_user_token() if self.is_authenticated() else None
        
        # Fetch dataset info
        ds_info = self.dataset_manager.get_dataset_by_id(dataset_id)
        if not ds_info:
            print(f"Dataset {dataset_id} not found")
            return None
        
        # Apply resource overrides if provided
        if resource_url:
            ds_info["url"] = resource_url
            ds_info["format"] = resource_format or ds_info["format"]
            ds_info["resource_name"] = resource_name or ds_info["resource_name"]
        
        # Prepare metadata
        dataset_raw = {"_id": ds_info.get("id")}  # Minimal raw dataset for metadata
        metadata = dataset_metadata_payload(dataset_raw, ds_info)
        
        layer_name = ds_info.get("title", "Unknown Dataset")
        if resource_name:
            layer_name = f"{layer_name} - {resource_name}"
        
        # Validate format and URL
        fmt = normalize_format(str(ds_info.get("format") or ""), str(ds_info.get("url") or ""))
        url = str(ds_info.get("url") or "")
        
        if not fmt or not url:
            print(f"Missing format or URL for dataset {dataset_id}")
            return None
        
        if not validate_url(url):
            print(f"URL {url} is not valid or not supported.")
            return None
        
        # Load layer based on format
        layer = None
        try:
            if fmt == "wfs":
                layer = load_wfs_layer(url, layer_name, parse_wms_url, get_wfs_typenames, token)
            elif fmt in ("geojson", "json", "gpkg", "shp", "xml"):
                layer = load_vector_layer(url, layer_name)
            elif fmt in ("wms", "wcs"):
                layer = load_raster_layer(url, layer_name, fmt, token, get_wms_layers, parse_wms_url)
            elif fmt == "3dtiles":
                layer = load_3d_layer(url, layer_name)
            elif fmt == "3dterrain":
                layer = load_terrain_layer(url, layer_name)
            elif fmt == "bim":
                layer = load_bim_layer(url, layer_name)
            elif fmt == "tilejson":
                layer = load_tileset_layer(url, layer_name)
            elif fmt == "3dpointclouds":
                layer = load_point_cloud_layer(url, layer_name)
            else:
                print(f"Unsupported format: {fmt}")
                return None
        except Exception as e:
            print(f"Failed to load layer: {str(e)}")
            return None
        
        # Apply metadata and optionally add to project
        if layer:
            try:
                apply_layer_metadata(layer, metadata)
                if add_to_project:
                    QgsProject.instance().addMapLayer(layer)
            except Exception as e:
                print(f"Failed to finalize layer: {str(e)}")
                return None
        
        return layer