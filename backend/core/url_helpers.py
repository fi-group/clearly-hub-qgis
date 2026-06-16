import re
import requests
from urllib.parse import parse_qs, urlparse, urlunparse
from defusedxml.ElementTree import fromstring as safe_fromstring

def validate_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False

    query = parse_qs(parsed.query)
    service = (query.get("service", [""])[0] or "").strip().lower()
    if service in {"wms", "wfs", "wcs"}:
        return True

    path_lower = (parsed.path or "").lower().rstrip("/")
    if path_lower.endswith(("/wms", "/wfs", "/wcs", "/ows")):
        return True

    url_lower = url.lower()
    if "tileset.json" in url_lower:
        return True
    if url_lower.endswith(".json") and ("3dtiles" in url_lower or "tiles" in url_lower):
        return True
    pattern = re.compile(r".*\.(wms|wfs|wcs|xml|geojson|json|3dtiles|bim)(\?.*)?$", re.IGNORECASE)
    if re.search(pattern, url):
        return True
    return False

def parse_ogc_base_url(url: str) -> str:
    """Strip all OGC service query parameters, returning only scheme+host+path."""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

# Keep alias so existing callers (WMS path) continue to work.
parse_wms_url = parse_ogc_base_url

def get_wfs_typenames(base_url: str, user_token: str = None):
    """Fetch WFS GetCapabilities and return all advertised FeatureType names."""
    try:
        caps_url = f"{base_url}?service=WFS&request=GetCapabilities"
        headers = {"Authorization": f"Bearer {user_token}"} if user_token else {}
        response = requests.get(caps_url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Failed to fetch WFS capabilities. Status: {response.status_code}")
            return []
        root = safe_fromstring(response.content)
        ns = root.tag.split("}")[0].strip("{") if "}" in root.tag else ""
        prefix = f"{{{ns}}}" if ns else ""
        typenames = []
        for ft in root.iter(f"{prefix}FeatureType"):
            name_el = ft.find(f"{prefix}Name")
            if name_el is not None and name_el.text:
                typenames.append(name_el.text.strip())
        return typenames
    except Exception as e:
        print(f"Failed to fetch WFS capabilities: {e}")
        return []

def get_wms_layers(base_url: str, user_token: str = None):
    try:
        caps_url = f"{base_url}?service=WMS&request=GetCapabilities"
        headers = {"Authorization": f"Bearer {user_token}"} if user_token else {}
        response = requests.get(caps_url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Failed to fetch WMS capabilities. Status: {response.status_code}")
            return []
        root = safe_fromstring(response.content)
        ns = root.tag.split("}")[0].strip("{") if "}" in root.tag else ""
        prefix = f"{{{ns}}}" if ns else ""
        layers = []
        for layer in root.iter(f"{prefix}Layer"):
            name_el = layer.find(f"{prefix}Name")
            if name_el is not None and name_el.text:
                layers.append(name_el.text)
        return layers
    except Exception as e:
        print(f"Failed to fetch WMS capabilities: {e}")
        return []
