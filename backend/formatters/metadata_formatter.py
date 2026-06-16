"""Metadata formatting for QGIS layers.

Handles QGIS-specific metadata application and layer property setting.
"""

from qgis.core import QgsLayerMetadata


def dataset_metadata_payload(dataset, dataset_info):
    """Generate metadata dictionary for QGIS layer.

    Args:
        dataset: Raw dataset dict from API.
        dataset_info: Normalized dataset info from dataset_formatter.

    Returns:
        Metadata dict with QGIS-compatible fields.
    """
    owner_hub = dataset.get("ownerHub") or {}
    resource = dataset_info.get("resources", [{}])[
        0] if dataset_info.get("resources") else {}
    tags = dataset.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, list):
        tags = []
    lic_val = dataset.get("license") or dataset.get("licence") or ""
    if isinstance(lic_val, list):
        licenses = [str(item) for item in lic_val if item]
    elif lic_val:
        licenses = [str(lic_val)]
    else:
        licenses = []
    return {
        "id": dataset_info.get("id") or "",
        "title": dataset_info.get("title") or "",
        "description": dataset_info.get("description") or "",
        "hub_name": owner_hub.get("name") or dataset_info.get("hub") or "",
        "hub_id": owner_hub.get("_id") or owner_hub.get("id") or "",
        "format": dataset_info.get("format") or "",
        "resource_name": dataset_info.get("resource_name") or resource.get("name") or "",
        "resource_id": resource.get("_id") or resource.get("id") or "",
        "resource_url": dataset_info.get("url") or resource.get("url") or "",
        "findability": dataset.get("findability") or "",
        "keywords": [str(t) for t in tags if t],
        "licenses": licenses,
    }


def apply_layer_metadata(layer, metadata):
    """Apply metadata to a QGIS layer and set custom properties.

    Args:
        layer: QgsMapLayer instance to update.
        metadata: Metadata dict from dataset_metadata_payload.

    Returns:
        True if metadata was applied successfully, False otherwise.
    """
    if layer is None:
        return False

    source_uri = ""
    try:
        source_uri = (layer.source() or "").strip()
    except Exception:
        pass

    if not source_uri:
        resource_url = (metadata.get("resource_url") or "").strip()
        if resource_url.startswith(("http://", "https://")):
            source_uri = f"url={resource_url}"
        elif resource_url:
            source_uri = resource_url

    if not source_uri:
        source_uri = metadata.get("id", "")

    # Set custom properties
    layer.setCustomProperty("clearlyhub/dataset_id", metadata.get("id", ""))
    layer.setCustomProperty("clearlyhub/identifier", source_uri)
    layer.setCustomProperty(
        "clearlyhub/hub_name",
        metadata.get(
            "hub_name",
            ""))
    layer.setCustomProperty("clearlyhub/hub_id", metadata.get("hub_id", ""))
    layer.setCustomProperty(
        "clearlyhub/resource_id",
        metadata.get(
            "resource_id",
            ""))
    layer.setCustomProperty(
        "clearlyhub/resource_name",
        metadata.get(
            "resource_name",
            ""))
    layer.setCustomProperty(
        "clearlyhub/resource_url",
        metadata.get(
            "resource_url",
            ""))
    layer.setCustomProperty("clearlyhub/format", metadata.get("format", ""))
    layer.setCustomProperty(
        "clearlyhub/findability",
        metadata.get(
            "findability",
            ""))

    try:
        layer_metadata = layer.metadata() or QgsLayerMetadata()
        if metadata.get("title"):
            layer_metadata.setTitle(metadata["title"])
        if metadata.get("description"):
            layer_metadata.setAbstract(metadata["description"])
        if source_uri:
            layer_metadata.setIdentifier(source_uri)
        if metadata.get("licenses"):
            layer_metadata.setLicenses(metadata["licenses"])
        keywords = metadata.get("keywords") or []
        if keywords:
            kw_map = layer_metadata.keywords() or {}
            kw_map["clearlyhub"] = keywords
            layer_metadata.setKeywords(kw_map)
        layer.setMetadata(layer_metadata)
    except Exception as e:
        print(f"Failed to apply QGIS metadata: {e}")
        return False

    return True
