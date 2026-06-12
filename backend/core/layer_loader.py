"""Layer loading helpers used by the ClearlyHub service layer.

This module centralizes provider-specific layer creation logic for vector,
raster, tiled scene, and point cloud sources.
"""

from urllib.parse import parse_qs, quote, urlparse

from qgis.core import QgsVectorLayer, QgsRasterLayer, QgsTiledSceneLayer, QgsPointCloudLayer


def load_vector_layer(url: str, layer_name: str):
    """Load a vector layer with the OGR provider.

    Args:
        url: Data source URL/path.
        layer_name: Name shown in QGIS.

    Returns:
        A valid QgsVectorLayer, or None when loading fails.
    """
    try:
        layer = QgsVectorLayer(url.strip(), layer_name, "ogr")
        if layer and layer.isValid():
            return layer
    except Exception as e:
        print(f"Failed to load vector layer: {e}")
    return None


def load_wfs_layer(url: str, layer_name: str, parse_base_func, get_typenames_func=None, user_token: str = None):
    """Load a WFS layer by discovering feature types from GetCapabilities.

    The resource URL is typically a GetCapabilities URL; the base endpoint is
    derived from it and queried for advertised FeatureType names. Each typename
    is tried in turn until a valid layer is produced.

    Args:
        url: WFS endpoint URL (may include request=GetCapabilities params).
        layer_name: Name shown in QGIS.
        parse_base_func: Callable that strips OGC query params from a URL.
        get_typenames_func: Callable(base_url, token) -> list[str] of typenames.
        user_token: Optional bearer token forwarded to capabilities request.

    Returns:
        A valid QgsVectorLayer, or None when loading fails.
    """
    try:
        base_url = parse_base_func(url.strip())

        # Discover feature types via GetCapabilities.
        typenames = []
        if get_typenames_func is not None:
            typenames = get_typenames_func(base_url, user_token) or []

        if not typenames:
            print(f"No WFS feature types found at: {base_url}")
            return None

        for typename in typenames:
            tn = quote(typename, safe=":,._-")
            for uri in (
                f"url={base_url}&service=WFS&typename={tn}&version=auto",
                f"url={base_url}&service=WFS&typeName={tn}&version=auto",
            ):
                layer = QgsVectorLayer(uri, f"{layer_name} – {typename}", "WFS")
                if layer and layer.isValid():
                    return layer

    except Exception as e:
        print(f"Failed to load WFS layer: {e}")
    return None


def load_raster_layer(url: str, layer_name: str, fmt: str, user_token: str, get_wms_layers_func, parse_base_func):
    """Load a raster layer for supported OGC raster services.

    Args:
        url: Service endpoint URL.
        layer_name: Name shown in QGIS.
        fmt: Dataset format identifier; ``wms`` and ``wcs`` are supported.
        user_token: Optional bearer token used by capabilities retrieval.
        get_wms_layers_func: Callable returning available WMS layer names.
        parse_base_func: Callable that strips query parameters from a URL.

    Returns:
        A valid QgsRasterLayer, or None when loading fails.
    """
    if fmt not in ("wms", "wcs"):
        print(f"Unsupported raster format: {fmt}")
        return None

    try:
        clean_url = url.strip()
        # Prefer direct use of the dataset URL before any normalization.
        for uri in (clean_url, f"url={clean_url}"):
            layer = QgsRasterLayer(uri, layer_name, fmt)
            if layer and layer.isValid():
                return layer

        base_url = parse_base_func(clean_url)

        if fmt == "wms":
            layers = get_wms_layers_func(base_url, user_token)
            if not layers:
                print(f"No layers found in WMS capabilities for: {base_url}")
                return None

            layer_name_param = layers[0]
            uri_variants = [
                f"url={base_url}&layers={layer_name_param}&styles=&format=image/png",
                f"url={base_url}&layers={layer_name_param}&styles=&format=image/png&crs=EPSG:3857",
                f"url={base_url}&layers={layer_name_param}&styles=&format=image/png&crs=EPSG:4326",
                f"url={base_url}&layers={layer_name_param}&styles=&format=image/png&crs=EPSG:28992",
            ]

            for uri in uri_variants:
                layer = QgsRasterLayer(uri, layer_name, "wms")
                if layer and layer.isValid():
                    return layer
            return None

        # WCS: try to preserve a coverage identifier if one is present in URL.
        parsed = urlparse(clean_url)
        query = parse_qs(parsed.query)
        coverage = None
        for key in ("coverage", "coverageid", "identifier", "layer", "layers"):
            values = query.get(key)
            if values:
                coverage = values[0]
                break

        uri_variants = []
        if coverage:
            cov = quote(coverage, safe=":,._-")
            uri_variants.extend(
                [
                    f"url={base_url}&identifier={cov}",
                    f"url={base_url}&coverage={cov}",
                    f"url={base_url}&coverageid={cov}",
                ]
            )
        uri_variants.append(f"url={base_url}")

        for uri in uri_variants:
            layer = QgsRasterLayer(uri, layer_name, "wcs")
            if layer and layer.isValid():
                return layer
    except Exception as e:
        print(f"Failed to load raster layer: {e}")
    return None


def tiled_scene_urls(url: str):
    """Build candidate tiled-scene URLs for compatibility fallbacks.

    Args:
        url: Input scene URL.

    Returns:
        Tuple of candidate URLs to try in order.
    """
    clean = url.strip()
    candidates = []
    lower = clean.lower()
    if "data.3dbag.nl" in lower and "/cesium3dtiles/" in lower:
        candidates.append("https://www.nederlandin3d.nl/viewer/datasource-data/6eae57c4-e429-4285-a77c-1f6e2c2e8eae/tileset.json")
    candidates.append(clean)
    return tuple(candidates)


def try_tiled_scene(url: str, layer_name: str, providers=("cesiumtiles", "tiledscene")):
    """Try loading a tiled scene with multiple providers and source forms.

    Args:
        url: Scene URL.
        layer_name: Name shown in QGIS.
        providers: Provider names to try in order.

    Returns:
        A valid QgsTiledSceneLayer, or None.
    """
    for scene_url in tiled_scene_urls(url):
        if scene_url != url.strip():
            print(f"Trying compatibility tiled scene URL: {scene_url}")
        for provider in providers:
            for source in (f"url={scene_url}", scene_url):
                layer = QgsTiledSceneLayer(source, layer_name, provider)
                if layer and layer.isValid():
                    print(f"Loaded 3D layer with provider '{provider}' and source '{source}'")
                    return layer
                if layer and layer.dataProvider():
                    err = layer.dataProvider().error().message()
                    if err:
                        print(f"Provider error ({provider}): {err}")
    print(f"3D layer could not be loaded: {url}")
    return None


def load_3d_layer(url: str, layer_name: str):
    """Load a 3D tiles scene using default scene providers."""
    return try_tiled_scene(url, layer_name, ("cesiumtiles", "tiledscene"))


def load_terrain_layer(url: str, layer_name: str):
    """Load a quantized mesh terrain scene using compatible providers."""
    return try_tiled_scene(url, layer_name, ("quantizedmesh", "cesiumtiles", "tiledscene"))


def load_bim_layer(url: str, layer_name: str):
    """Load a BIM scene using tiled-scene compatible providers."""
    return try_tiled_scene(url, layer_name, ("cesiumtiles", "tiledscene"))


def load_tileset_layer(url: str, layer_name: str):
    """Load a generic tileset scene using tiled-scene providers."""
    return try_tiled_scene(url, layer_name, ("cesiumtiles", "tiledscene"))


def point_cloud_providers_for_url(url: str):
    """Return preferred point-cloud providers based on URL signature."""
    u = url.strip().lower()
    if u.endswith("ept.json"):
        return ("ept", "pdal")
    if ".copc." in u or u.endswith(".copc") or u.endswith(".copc.laz"):
        return ("copc", "pdal")
    return ("pdal", "copc", "ept")


def point_cloud_sources_for_url(url: str):
    """Return candidate point-cloud source URIs for local and remote data."""
    src = url.strip()
    if src.startswith(("http://", "https://")):
        return (src, f"/vsicurl/{src}")
    return (src,)


def load_point_cloud_layer(url: str, layer_name: str):
    """Load a point cloud by trying provider/source combinations.

    Args:
        url: Point cloud URL/path.
        layer_name: Name shown in QGIS.

    Returns:
        A valid QgsPointCloudLayer, or None.
    """
    try:
        providers = point_cloud_providers_for_url(url)
        sources = point_cloud_sources_for_url(url)
        for provider in providers:
            for source in sources:
                layer = QgsPointCloudLayer(source, layer_name, provider)
                if layer and layer.isValid():
                    print(f"Loaded point cloud with provider '{provider}' and source '{source}'")
                    return layer
                if layer and layer.dataProvider():
                    err = layer.dataProvider().error().message()
                    if err:
                        print(f"Provider error ({provider}): {err}")
        print(f"Point cloud could not be loaded: {url}")
        return None
    except Exception as e:
        print(f"Failed to load point cloud layer: {e}")
        return None
