import unittest
from unittest.mock import MagicMock
from uptime_kuma_api.api import UptimeKumaApi


class TestStatusPageV2(unittest.TestCase):
    """Unit tests for _build_status_page_data version-gated behavior.

    These tests mock the version attribute and call _build_status_page_data
    directly — no live server connection required.
    """

    def setUp(self):
        self.api_v2 = MagicMock(spec=UptimeKumaApi)
        self.api_v2.version = "2.4.0"
        self.build_v2 = UptimeKumaApi._build_status_page_data.__get__(self.api_v2)

        self.api_v1 = MagicMock(spec=UptimeKumaApi)
        self.api_v1.version = "1.23.2"
        self.build_v1 = UptimeKumaApi._build_status_page_data.__get__(self.api_v1)

    # --- Test 1: v2 analytics fields included when provided ---
    def test_v2_analytics_fields_included(self):
        _, config, _, _ = self.build_v2(
            slug="test", id=1, title="Test Page",
            analyticsType="plausible",
            analyticsId="my-domain.com",
            analyticsScriptUrl="https://plausible.io/js/script.js",
        )
        self.assertEqual(config["analyticsType"], "plausible")
        self.assertEqual(config["analyticsId"], "my-domain.com")
        self.assertEqual(config["analyticsScriptUrl"], "https://plausible.io/js/script.js")

    # --- Test 2: v2 googleAnalyticsId omitted from config ---
    def test_v2_google_analytics_id_omitted(self):
        _, config, _, _ = self.build_v2(
            slug="test", id=1, title="Test Page",
            googleAnalyticsId="UA-12345",
        )
        self.assertNotIn("googleAnalyticsId", config)

    # --- Test 3: v1 googleAnalyticsId included in config ---
    def test_v1_google_analytics_id_included(self):
        _, config, _, _ = self.build_v1(
            slug="test", id=1, title="Test Page",
            googleAnalyticsId="UA-12345",
        )
        self.assertIn("googleAnalyticsId", config)
        self.assertEqual(config["googleAnalyticsId"], "UA-12345")

    # --- Test 4: v1 v2 analytics params silently discarded ---
    def test_v1_v2_analytics_params_discarded(self):
        _, config, _, _ = self.build_v1(
            slug="test", id=1, title="Test Page",
            analyticsType="plausible",
            analyticsId="my-domain.com",
            analyticsScriptUrl="https://plausible.io/js/script.js",
        )
        self.assertNotIn("analyticsType", config)
        self.assertNotIn("analyticsId", config)
        self.assertNotIn("analyticsScriptUrl", config)

    # --- Test 5: v2 password omitted even when provided ---
    def test_v2_password_omitted(self):
        _, config, _, _ = self.build_v2(
            slug="test", id=1, title="Test Page",
            password="secret123",
        )
        self.assertNotIn("password", config)

    # --- Test 6: v1 password included when provided ---
    def test_v1_password_included(self):
        _, config, _, _ = self.build_v1(
            slug="test", id=1, title="Test Page",
            password="secret123",
        )
        self.assertIn("password", config)
        self.assertEqual(config["password"], "secret123")

    # --- Test 7: v1 password omitted when not provided ---
    def test_v1_password_omitted_when_not_provided(self):
        _, config, _, _ = self.build_v1(
            slug="test", id=1, title="Test Page",
        )
        self.assertNotIn("password", config)

    # --- Test 8: v2 showOnlyLastHeartbeat and rssTitle included when provided ---
    def test_v2_new_fields_included(self):
        _, config, _, _ = self.build_v2(
            slug="test", id=1, title="Test Page",
            showOnlyLastHeartbeat=True,
            rssTitle="Custom RSS Title",
        )
        self.assertEqual(config["showOnlyLastHeartbeat"], True)
        self.assertEqual(config["rssTitle"], "Custom RSS Title")

    # --- Test 9: v2 showOnlyLastHeartbeat and rssTitle omitted when None ---
    def test_v2_new_fields_omitted_when_none(self):
        _, config, _, _ = self.build_v2(
            slug="test", id=1, title="Test Page",
            showOnlyLastHeartbeat=None,
            rssTitle=None,
        )
        self.assertNotIn("showOnlyLastHeartbeat", config)
        self.assertNotIn("rssTitle", config)

    # --- Test 10: v1 showOnlyLastHeartbeat and rssTitle omitted regardless of value ---
    def test_v1_new_fields_omitted_regardless(self):
        _, config, _, _ = self.build_v1(
            slug="test", id=1, title="Test Page",
            showOnlyLastHeartbeat=True,
            rssTitle="Custom RSS Title",
        )
        self.assertNotIn("showOnlyLastHeartbeat", config)
        self.assertNotIn("rssTitle", config)


if __name__ == '__main__':
    unittest.main()
