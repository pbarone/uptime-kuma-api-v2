import unittest
from unittest.mock import MagicMock, patch
from uptime_kuma_api.api import UptimeKumaApi


class TestStatusPageV2(unittest.TestCase):
    """Unit tests for _build_status_page_data version-gated behavior.

    These tests mock the version attribute and call _build_status_page_data
    directly — no live server connection required.
    """

    def setUp(self):
        self.api_v2 = MagicMock(spec=UptimeKumaApi)
        self.api_v2.version = "2.4.0"
        # bind the real version-gate choke point so gates parse self.version
        self.api_v2._parsed_version = UptimeKumaApi._parsed_version.__get__(self.api_v2)
        self.build_v2 = UptimeKumaApi._build_status_page_data.__get__(self.api_v2)

        self.api_v1 = MagicMock(spec=UptimeKumaApi)
        self.api_v1.version = "1.23.2"
        self.api_v1._parsed_version = UptimeKumaApi._parsed_version.__get__(self.api_v1)
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

    # --- Test 11: v2 analytics keys must be PRESENT even when None ---
    def test_v2_analytics_keys_always_present_when_none(self):
        """Regression: the v2 server rejects the save with "Invalid analytics
        type" when analyticsType is absent from the payload. Verified against
        2.4.0: null is accepted, an absent key is not. Omitting the key broke
        save_status_page for every page with no analytics configured, which in
        turn broke post_incident and unpin_incident (both call save)."""
        _, config, _, _ = self.build_v2(slug="test", id=1, title="Test Page")
        self.assertIn("analyticsType", config)
        self.assertIsNone(config["analyticsType"])
        self.assertIn("analyticsId", config)
        self.assertIn("analyticsScriptUrl", config)

    # --- Test 12: explicit None is still sent as null, not dropped ---
    def test_v2_analytics_explicit_none_sent_as_null(self):
        _, config, _, _ = self.build_v2(
            slug="test", id=1, title="Test Page",
            analyticsType=None, analyticsId=None, analyticsScriptUrl=None,
        )
        self.assertIsNone(config["analyticsType"])
        self.assertIsNone(config["analyticsId"])
        self.assertIsNone(config["analyticsScriptUrl"])

    # --- Test 13: v1 must NOT gain the v2 analytics keys ---
    def test_v1_analytics_keys_absent_when_none(self):
        _, config, _, _ = self.build_v1(slug="test", id=1, title="Test Page")
        self.assertNotIn("analyticsType", config)
        self.assertNotIn("analyticsId", config)
        self.assertNotIn("analyticsScriptUrl", config)


class TestGetStatusPageSslVerify(unittest.TestCase):
    """Bug B (#65): ``ssl_verify`` must reach the ``get_status_page`` HTTP fetch.

    ``__init__`` funnels ``ssl_verify`` into ``socketio.Client`` only and never
    stores it on the instance, so ``get_status_page``'s ``requests.get`` call
    omits any ``verify=`` argument. A caller that asked for ``ssl_verify=False``
    still gets TLS verification on the HTTP leg and fails against a self-signed
    certificate.

    No live server: ``socketio.Client``/``connect`` are patched, ``_call`` is
    stubbed, and ``requests.get`` is a mock whose call kwargs are inspected.
    """

    # Minimal HTTP payload shaped like /api/status-page/<slug>.
    HTTP_PAYLOAD = {
        "config": {"slug": "slug1", "title": "status page 1"},
        "incident": None,
        "publicGroupList": [],
        "maintenanceList": [],
    }

    @staticmethod
    def _build_api(ssl_verify):
        """Construct an UptimeKumaApi with the transport fully mocked."""
        with patch('uptime_kuma_api.api.UptimeKumaApi.connect'), \
                patch('uptime_kuma_api.api.socketio.Client') as mock_client_cls:
            mock_client_cls.return_value = MagicMock()
            api = UptimeKumaApi("https://fake:3001", ssl_verify=ssl_verify)
        # The socket.io leg is not under test here; only the HTTP leg is.
        api._call = MagicMock(return_value={"config": {}})
        return api

    def _fetch_status_page(self, ssl_verify, payload=None):
        """Call get_status_page and return the mocked requests.get."""
        _, mock_get = self._fetch_status_page_result(ssl_verify, payload)
        return mock_get

    def _fetch_status_page_result(self, ssl_verify, payload=None):
        """Call get_status_page; return (returned dict, mocked requests.get)."""
        api = self._build_api(ssl_verify)
        with patch('uptime_kuma_api.api.requests.get') as mock_get:
            mock_get.return_value.json.return_value = (
                self.HTTP_PAYLOAD if payload is None else payload
            )
            page = api.get_status_page("slug1")
        return page, mock_get

    # --- Property 3: Bug Condition - verify forwarded when ssl_verify=False ---
    def test_ssl_verify_false_forwarded_to_requests_get(self):
        """ssl_verify=False must be forwarded as verify=False to requests.get.

        **Validates: Requirements 2.4, 2.5**

        Bug condition: isBugCondition_B(X) - X.performsRequestsGet AND
        X.ssl_verify = False. EXPECTED TO FAIL on unfixed code, where the
        request carries only ``timeout=`` and no ``verify=`` at all.
        """
        mock_get = self._fetch_status_page(ssl_verify=False)

        mock_get.assert_called_once()
        kwargs = mock_get.call_args.kwargs
        self.assertIn(
            "verify", kwargs,
            "requests.get was called without any verify= argument "
            f"(kwargs={kwargs!r}); ssl_verify=False was ignored on the HTTP leg",
        )
        self.assertFalse(
            kwargs["verify"],
            f"expected verify=False, got verify={kwargs['verify']!r}",
        )

    # ------------------------------------------------------------------
    # Property 4: Preservation - default ssl_verify=True path unchanged
    #
    # These assert the OUTSIDE of the bug condition (¬isBugCondition_B):
    # with the default ssl_verify=True, get_status_page must keep returning
    # exactly the dict structure it returned before the fix, including the
    # incident/incidents dual-key shape, the merged config, and the existing
    # requests.get arguments (URL + timeout).
    #
    # The complementary `verify=True` assertion could not hold on the unfixed
    # code (no `verify=` was passed at all), so it was deferred out of the
    # pre-fix baseline; it now lives in
    # test_default_forwards_verify_true_to_requests_get below.
    # ------------------------------------------------------------------

    # Incident object as the server sends it, pre-style-parsing.
    INCIDENT = {
        "id": 1,
        "title": "title 1",
        "content": "content 1",
        "style": "danger",
        "pin": 1,
        "createdDate": "2022-12-15 16:51:43",
        "lastUpdatedDate": None,
    }

    def test_default_forwards_verify_true_to_requests_get(self):
        """The default ssl_verify=True is forwarded as verify=True.

        **Validates: Requirements 3.3**

        Complement of the bug-condition test: honouring ``ssl_verify=False``
        must not weaken the default, which has to keep verifying certificates
        on the HTTP leg as well as the socket.io leg.
        """
        mock_get = self._fetch_status_page(ssl_verify=True)

        mock_get.assert_called_once()
        kwargs = mock_get.call_args.kwargs
        self.assertIn(
            "verify", kwargs,
            "requests.get was called without any verify= argument "
            f"(kwargs={kwargs!r}); the default ssl_verify=True is not forwarded",
        )
        self.assertTrue(
            kwargs["verify"],
            f"expected verify=True on the default path, got verify={kwargs['verify']!r}",
        )

    def test_default_returns_unchanged_top_level_shape(self):
        """Default path returns the same keys/values as before the fix.

        **Validates: Requirements 3.3, 3.4**

        ``_call`` contributes ``{"config": {}}`` and the HTTP leg contributes
        ``{"slug", "title"}``, so the merged result is exactly the config keys
        plus the four synthesised keys.
        """
        page, _ = self._fetch_status_page_result(ssl_verify=True)

        self.assertEqual(
            set(page),
            {"slug", "title", "incident", "incidents", "publicGroupList", "maintenanceList"},
        )
        self.assertEqual(page["slug"], "slug1")
        self.assertEqual(page["title"], "status page 1")
        self.assertIsNone(page["incident"])
        self.assertEqual(page["incidents"], [])
        self.assertEqual(page["publicGroupList"], [])
        self.assertEqual(page["maintenanceList"], [])

    def test_default_preserves_existing_requests_get_arguments(self):
        """The URL and timeout passed to requests.get are unchanged.

        **Validates: Requirements 3.3**
        """
        api = self._build_api(ssl_verify=True)
        with patch('uptime_kuma_api.api.requests.get') as mock_get:
            mock_get.return_value.json.return_value = self.HTTP_PAYLOAD
            api.get_status_page("slug1")

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args, (f"{api.url}/api/status-page/slug1",))
        self.assertEqual(kwargs["timeout"], api.timeout)

    def test_default_preserves_incident_incidents_dual_key_shape(self):
        """Both keys are present and consistent for every server payload shape.

        **Validates: Requirements 3.4**

        Scoped property: for each incident payload variant the 2.x and 1.x
        servers can send, the returned dict exposes ``incidents`` as a list and
        ``incident`` as its first entry (or ``None`` when empty).
        """
        from uptime_kuma_api import IncidentStyle

        second = dict(self.INCIDENT, id=2, title="title 2", style="info")
        variants = [
            # (label, incident-related payload keys, expected incident ids)
            ("v2 array", {"incidents": [dict(self.INCIDENT)]}, [1]),
            ("v2 multiple", {"incidents": [dict(self.INCIDENT), dict(second)]}, [1, 2]),
            ("v2 empty array", {"incidents": []}, []),
            ("v2 null array", {"incidents": None}, []),
            ("v1 singular", {"incident": dict(self.INCIDENT)}, [1]),
            ("v1 null singular", {"incident": None}, []),
            ("neither key", {}, []),
        ]

        for label, incident_keys, expected_ids in variants:
            with self.subTest(payload=label):
                payload = {
                    "config": {"slug": "slug1", "title": "status page 1"},
                    "publicGroupList": [],
                    "maintenanceList": [],
                    **incident_keys,
                }
                page, _ = self._fetch_status_page_result(ssl_verify=True, payload=payload)

                self.assertIn("incident", page)
                self.assertIn("incidents", page)
                self.assertIsInstance(page["incidents"], list)
                self.assertEqual([i["id"] for i in page["incidents"]], expected_ids)
                if expected_ids:
                    self.assertEqual(page["incident"], page["incidents"][0])
                    # style parsing still applies to every incident
                    self.assertEqual(page["incidents"][0]["style"], IncidentStyle.DANGER)
                else:
                    self.assertIsNone(page["incident"])

    def test_default_preserves_public_group_list_send_url_conversion(self):
        """publicGroupList monitors keep their int -> bool sendUrl conversion.

        **Validates: Requirements 3.4**
        """
        payload = {
            "config": {"slug": "slug1", "title": "status page 1"},
            "incident": None,
            "publicGroupList": [{
                "id": 1,
                "name": "Services",
                "weight": 1,
                "monitorList": [{"id": 1, "name": "monitor 1", "type": "http", "sendUrl": 0}],
            }],
            "maintenanceList": [],
        }

        page, _ = self._fetch_status_page_result(ssl_verify=True, payload=payload)

        monitor = page["publicGroupList"][0]["monitorList"][0]
        self.assertIs(monitor["sendUrl"], False)


if __name__ == '__main__':
    unittest.main()
