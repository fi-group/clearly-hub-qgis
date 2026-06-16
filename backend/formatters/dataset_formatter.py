"""Pure data transformation functions for datasets.

No external dependencies, no side effects. These functions normalize,
sanitize, and reshape raw API responses into standardized structures.
"""


def normalize_format(fmt: str, url: str = "") -> str:
    """Normalize dataset format strings and infer from URL if needed.

    Args:
        fmt: Format string (e.g., "application/geo+json", "wms").
        url: Optional URL to infer format from if fmt is empty/unknown.

    Returns:
        Normalized format identifier (lowercase, aliased).
    """
    fmt = (fmt or "").strip().lower()
    url = (url or "").strip().lower()

    aliases = {
        "application/geo+json": "geojson",
        "geo+json": "geojson",
        "application/json": "json",
        "3d tiles": "3dtiles",
        "3d_tile": "3dtiles",
        "3d tile": "3dtiles",
        "wms": "wms",
        "wfs": "wfs"
    }
    fmt = aliases.get(fmt, fmt)

    if not fmt or fmt in {"unknown", "unknown format"}:
        if "tileset.json" in url or "/3dtiles" in url or "3dtiles" in url:
            return "3dtiles"
        if url.endswith(".geojson"):
            return "geojson"
        if url.endswith(".json"):
            return "json"
    return fmt


def get_primary_resource(dataset: dict):
    """Return the first resource with a URL.

    Args:
        dataset: Raw dataset dict from API.

    Returns:
        First resource dict with a URL, or first resource if none have URLs, or None.
    """
    if not dataset:
        return None
    resources = dataset.get("resources") or []
    for r in resources:
        if r.get("url"):
            return r
    return resources[0] if resources else None


def dedupe_preserve_order(values):
    """Return non-empty string values without duplicates, preserving order.

    Args:
        values: Iterable of values to dedupe.

    Returns:
        List of unique, non-empty strings in original order.
    """
    seen = set()
    result = []
    for v in values or []:
        text = str(v or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def extract_named_values(value,
                         text_keys=("name", "title", "label", "value"),
                         fallback_keys=("_id", "id")):
    """Extract readable string values from strings, dicts, or nested collections.

    Handles multiple input types and searches for readable fields by priority.

    Args:
        value: String, dict, or nested collection to extract from.
        text_keys: Priority-ordered field names to search in dicts.
        fallback_keys: Lower-priority fallback field names.

    Returns:
        List of extracted, deduplicated strings.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        collected = []
        for item in value:
            collected.extend(
                extract_named_values(
                    item, text_keys, fallback_keys))
        return dedupe_preserve_order(collected)
    if isinstance(value, dict):
        for key in text_keys:
            text = str(value.get(key) or "").strip()
            if text:
                return [text]
        for key in fallback_keys:
            text = str(value.get(key) or "").strip()
            if text:
                return [text]
        return []
    text = str(value).strip()
    return [text] if text else []


def extract_hub_names(hub_value):
    """Extract one or more readable hub names from supported hub shapes.

    Args:
        hub_value: Hub value (string, dict, or nested collection).

    Returns:
        List of hub name strings.
    """
    return extract_named_values(hub_value)


def extract_part_of_hub_names(dataset):
    """Extract part-of-hub names using common API field variants.

    Args:
        dataset: Dataset dict with potential parent-hub fields.

    Returns:
        List of parent hub names or empty list.
    """
    for key in ("partOfHub", "partOfHubs", "partOf", "parentHub"):
        names = extract_hub_names(dataset.get(key))
        if names:
            return names
    return []


def extract_profile_picture_url(dataset):
    """Extract profile picture URL from supported dataset fields.

    Args:
        dataset: Dataset dict with potential profile picture URL fields.

    Returns:
        Profile picture URL string, or empty string when unavailable.
    """
    if not dataset:
        return ""

    def _valid_url(value):
        text = str(value or "").strip()
        if not (text.startswith("http://") or text.startswith("https://")):
            return ""
        lowered = text.lower()
        if "/null" in lowered or lowered.endswith("/public/"):
            return ""
        return text

    # Direct preview fields on the dataset.
    for key in (
        "previewImage",
        "landscapePreviewImage",
        "previewInfoImage",
        "profilepictureurl",
        "profilePictureUrl",
        "profile_picture_url",
    ):
        url = _valid_url(dataset.get(key))
        if url:
            return url

    # Preview from owner hub participants.
    owner_hub = dataset.get("ownerHub") or {}
    participants = owner_hub.get(
        "participants") if isinstance(owner_hub, dict) else []
    for participant in participants or []:
        if not isinstance(participant, dict):
            continue
        url = _valid_url(participant.get("profilePictureUrl"))
        if url:
            return url

    return ""


def extract_tags(tags_value):
    """Extract readable tag values from strings, dicts, and collections.

    Args:
        tags_value: Tags as string (comma-separated), dict, or nested collection.

    Returns:
        List of tag strings, deduplicated.
    """
    if isinstance(tags_value, str):
        parts = [p.strip() for p in tags_value.split(",")]
        return dedupe_preserve_order(parts)
    return extract_named_values(tags_value, text_keys=(
        "name", "title", "label", "value", "slug"), fallback_keys=())


def dataset_formats(dataset, primary_resource=None):
    """Return normalized format identifiers from dataset and resources.

    Args:
        dataset: Dataset dict with resources.
        primary_resource: Optional pre-fetched primary resource.

    Returns:
        List of normalized format identifiers.
    """
    primary = primary_resource or get_primary_resource(dataset) or {}
    formats = []
    primary_fmt = normalize_format(
        primary.get("format") or dataset.get("format") or "",
        primary.get("url") or dataset.get("url") or "",
    )
    if primary_fmt:
        formats.append(primary_fmt)
    for res in dataset.get("resources") or []:
        f = normalize_format(res.get("format") or "", res.get("url") or "")
        if f:
            formats.append(f)
    return dedupe_preserve_order(formats)


def build_dataset_info(dataset):
    """Clean dataset information for standardized use.

    Transforms raw API dataset into normalized internal format with
    all required fields for UI rendering and layer loading.

    Args:
        dataset: Raw dataset dict from API.

    Returns:
        Normalized dataset info dict with fields: id, title, description,
        hub, owner_hub, part_of_hub, part_of_hubs, tags, findability,
        format, formats, url, resource_name, resources.
    """
    resource = get_primary_resource(dataset) or {}
    owner_hubs = extract_hub_names(dataset.get("ownerHub"))
    owner_hub = owner_hubs[0] if owner_hubs else "No Hub"
    part_of_hubs = extract_part_of_hub_names(dataset)
    tags = extract_tags(dataset.get("tags") or [])
    formats = dataset_formats(dataset, primary_resource=resource)
    resources = [
        {
            "id": r.get("_id") or r.get("id") or "",
            "name": r.get("name") or "",
            "url": r.get("url") or "",
            "format": r.get("format") or "",
        }
        for r in (dataset.get("resources") or []) if r.get("url")
    ]
    profile_picture_url = extract_profile_picture_url(dataset)
    return {
        "id": dataset.get("_id") or dataset.get("id"),
        "title": dataset.get("title") or "No Title",
        "description": dataset.get("description") or "No Description",
        "hub": owner_hub,
        "owner_hub": owner_hub,
        "part_of_hub": part_of_hubs[0] if part_of_hubs else "",
        "part_of_hubs": part_of_hubs,
        "tags": tags,
        "findability": dataset.get("findability") or "",
        "format": resource.get("format") or "Unknown Format",
        "formats": formats,
        "url": resource.get("url") or "",
        "resource_name": resource.get("name") or "",
        "resources": resources,
        "profile_picture_url": profile_picture_url,
    }
