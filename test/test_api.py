import unittest

from backend.core.url_helpers import validate_url


class TestUrlValidation(unittest.TestCase):
    """Unit tests for URL validation helper behavior."""

    def test_accepts_wms_service_query(self):
        self.assertTrue(validate_url("https://example.com/geoserver/ows?service=WMS&request=GetCapabilities"))

    def test_accepts_wms_path_endpoint(self):
        self.assertTrue(validate_url("https://example.com/geoserver/wms"))

    def test_rejects_non_service_generic_http_url(self):
        self.assertFalse(validate_url("https://example.com/catalog"))


if __name__ == "__main__":
    unittest.main()
