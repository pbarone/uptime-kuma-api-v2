"""
Unit tests for new monitor parameters in _build_monitor_data.

These tests mock the API version and call _build_monitor_data directly
without connecting to a live server.
"""
import unittest
from unittest.mock import MagicMock

from uptime_kuma_api import MonitorType, AuthMethod
from uptime_kuma_api.api import UptimeKumaApi


class TestMonitorParamsV2(unittest.TestCase):
    """Tests for v2 monitor parameter handling in _build_monitor_data."""

    def setUp(self):
        self.api = MagicMock(spec=UptimeKumaApi)
        self.api.version = "2.4.0"
        self.build = UptimeKumaApi._build_monitor_data.__get__(self.api)

    def _build_v1(self):
        """Return a _build_monitor_data bound to a v1 mock."""
        api = MagicMock(spec=UptimeKumaApi)
        api.version = "1.23.2"
        return UptimeKumaApi._build_monitor_data.__get__(api)

    # ─── 1. jsonPathOperator ──────────────────────────────────────────

    def test_json_path_operator_included_for_json_query(self):
        """jsonPathOperator is included when type is JSON_QUERY."""
        result = self.build(
            type=MonitorType.JSON_QUERY,
            name="test",
            jsonPath="$.status",
            expectedValue="ok",
            jsonPathOperator="contains",
        )
        self.assertEqual(result["jsonPathOperator"], "contains")

    def test_json_path_operator_omitted_for_http(self):
        """jsonPathOperator is NOT included for non-JSON_QUERY types."""
        result = self.build(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            jsonPathOperator="contains",
        )
        self.assertNotIn("jsonPathOperator", result)

    def test_json_path_operator_omitted_for_ping(self):
        """jsonPathOperator is NOT included for PING type."""
        result = self.build(
            type=MonitorType.PING,
            name="test",
            hostname="127.0.0.1",
            jsonPathOperator=">=",
        )
        self.assertNotIn("jsonPathOperator", result)

    def test_json_path_operator_omitted_when_none(self):
        """jsonPathOperator is NOT included when None (even for JSON_QUERY)."""
        result = self.build(
            type=MonitorType.JSON_QUERY,
            name="test",
            jsonPath="$.status",
            expectedValue="ok",
            jsonPathOperator=None,
        )
        self.assertNotIn("jsonPathOperator", result)

    # ─── 2. ipFamily version gate ─────────────────────────────────────

    def test_ip_family_included_for_network_type_v2(self):
        """ipFamily is included for network types on v2."""
        for mtype in [MonitorType.HTTP, MonitorType.PING, MonitorType.PORT,
                      MonitorType.DNS, MonitorType.MQTT, MonitorType.SNMP]:
            result = self.build(type=mtype, name="test", hostname="h", ipFamily="IPv4")
            self.assertIn("ipFamily", result, f"ipFamily missing for {mtype}")
            self.assertEqual(result["ipFamily"], "IPv4")

    def test_ip_family_omitted_for_network_type_v1(self):
        """ipFamily is omitted for network types on v1."""
        build_v1 = self._build_v1()
        for mtype in [MonitorType.HTTP, MonitorType.PING, MonitorType.PORT,
                      MonitorType.DNS, MonitorType.MQTT]:
            result = build_v1(type=mtype, name="test", hostname="h", ipFamily="IPv4")
            self.assertNotIn("ipFamily", result, f"ipFamily should not be in v1 for {mtype}")

    def test_ip_family_omitted_for_non_network_type_v2(self):
        """ipFamily is omitted for non-network types (e.g., DOCKER) even on v2."""
        result = self.build(
            type=MonitorType.DOCKER,
            name="test",
            docker_container="c",
            docker_host=1,
            ipFamily="IPv6",
        )
        self.assertNotIn("ipFamily", result)

    def test_ip_family_omitted_when_none_v2(self):
        """ipFamily is omitted when None even for network types on v2."""
        result = self.build(type=MonitorType.HTTP, name="test", ipFamily=None)
        self.assertNotIn("ipFamily", result)

    # ─── 3. HTTP params version gate ──────────────────────────────────

    def test_http_params_included_for_http_family_v2(self):
        """HTTP v2 params are included for HTTP-family types on v2."""
        result = self.build(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            cacheBust=True,
            retryOnlyOnStatusCodeFailure=False,
            bearer_token="tok123",
            oauth_audience="aud",
            domainExpiryNotification=True,
            saveResponse=True,
            saveErrorResponse=False,
            responseMaxLength=5000,
            responsecheck="check",
        )
        self.assertTrue(result["cacheBust"])
        self.assertFalse(result["retryOnlyOnStatusCodeFailure"])
        self.assertEqual(result["bearer_token"], "tok123")
        self.assertEqual(result["oauth_audience"], "aud")
        self.assertTrue(result["domainExpiryNotification"])
        self.assertTrue(result["saveResponse"])
        self.assertFalse(result["saveErrorResponse"])
        self.assertEqual(result["responseMaxLength"], 5000)
        self.assertEqual(result["responsecheck"], "check")

    def test_http_params_omitted_on_v1(self):
        """HTTP v2 params are omitted on v1 even for HTTP-family types."""
        build_v1 = self._build_v1()
        result = build_v1(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            cacheBust=True,
            bearer_token="tok",
            saveResponse=True,
            responseMaxLength=1000,
        )
        self.assertNotIn("cacheBust", result)
        self.assertNotIn("bearer_token", result)
        self.assertNotIn("saveResponse", result)
        self.assertNotIn("responseMaxLength", result)

    def test_http_params_omitted_for_non_http_family_v2(self):
        """HTTP v2 params are omitted for non-HTTP-family types like PING."""
        result = self.build(
            type=MonitorType.PING,
            name="test",
            hostname="127.0.0.1",
            cacheBust=True,
            bearer_token="tok",
        )
        self.assertNotIn("cacheBust", result)
        self.assertNotIn("bearer_token", result)

    def test_http_params_none_not_included(self):
        """HTTP v2 params left as None are not included in output."""
        result = self.build(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            cacheBust=None,
            bearer_token=None,
        )
        self.assertNotIn("cacheBust", result)
        self.assertNotIn("bearer_token", result)

    # ─── 4. responseMaxLength boundary validation ─────────────────────

    def test_response_max_length_zero_raises(self):
        """responseMaxLength=0 raises ValueError."""
        with self.assertRaises(ValueError):
            self.build(
                type=MonitorType.HTTP,
                name="test",
                url="http://example.com",
                responseMaxLength=0,
            )

    def test_response_max_length_too_large_raises(self):
        """responseMaxLength=10_000_001 raises ValueError."""
        with self.assertRaises(ValueError):
            self.build(
                type=MonitorType.HTTP,
                name="test",
                url="http://example.com",
                responseMaxLength=10_000_001,
            )

    def test_response_max_length_minimum_ok(self):
        """responseMaxLength=1 is valid (lower boundary)."""
        result = self.build(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            responseMaxLength=1,
        )
        self.assertEqual(result["responseMaxLength"], 1)

    def test_response_max_length_maximum_ok(self):
        """responseMaxLength=10_000_000 is valid (upper boundary)."""
        result = self.build(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            responseMaxLength=10_000_000,
        )
        self.assertEqual(result["responseMaxLength"], 10_000_000)

    def test_response_max_length_negative_raises(self):
        """responseMaxLength=-1 raises ValueError."""
        with self.assertRaises(ValueError):
            self.build(
                type=MonitorType.HTTP,
                name="test",
                url="http://example.com",
                responseMaxLength=-1,
            )

    # ─── 5. PING params ──────────────────────────────────────────────

    def test_ping_params_included_for_ping_type(self):
        """PING-specific params are included for PING type."""
        result = self.build(
            type=MonitorType.PING,
            name="test",
            hostname="127.0.0.1",
            ping_count=5,
            ping_numeric=True,
            ping_per_request_timeout=10,
        )
        self.assertEqual(result["ping_count"], 5)
        self.assertTrue(result["ping_numeric"])
        self.assertEqual(result["ping_per_request_timeout"], 10)

    def test_ping_params_omitted_for_non_ping_type(self):
        """PING-specific params are NOT included for HTTP type."""
        result = self.build(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            ping_count=5,
            ping_numeric=True,
            ping_per_request_timeout=10,
        )
        self.assertNotIn("ping_count", result)
        self.assertNotIn("ping_numeric", result)
        self.assertNotIn("ping_per_request_timeout", result)

    def test_ping_params_none_omitted(self):
        """PING params left as None are not included even for PING type."""
        result = self.build(
            type=MonitorType.PING,
            name="test",
            hostname="127.0.0.1",
            ping_count=None,
            ping_numeric=None,
        )
        self.assertNotIn("ping_count", result)
        self.assertNotIn("ping_numeric", result)

    # ─── 6. MQTT params ──────────────────────────────────────────────

    def test_mqtt_params_included_for_mqtt_type(self):
        """MQTT new params are included for MQTT type."""
        result = self.build(
            type=MonitorType.MQTT,
            name="test",
            hostname="broker.local",
            port=1883,
            mqttWebsocketPath="/ws",
            mqttCheckType="keyword",
        )
        self.assertEqual(result["mqttWebsocketPath"], "/ws")
        self.assertEqual(result["mqttCheckType"], "keyword")

    def test_mqtt_params_omitted_for_non_mqtt_type(self):
        """MQTT new params are NOT included for HTTP type."""
        result = self.build(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            mqttWebsocketPath="/ws",
            mqttCheckType="keyword",
        )
        self.assertNotIn("mqttWebsocketPath", result)
        self.assertNotIn("mqttCheckType", result)

    def test_mqtt_check_type_json_query_valid(self):
        """mqttCheckType='json-query' is valid."""
        result = self.build(
            type=MonitorType.MQTT,
            name="test",
            hostname="broker.local",
            mqttCheckType="json-query",
        )
        self.assertEqual(result["mqttCheckType"], "json-query")

    def test_mqtt_check_type_invalid_raises(self):
        """Invalid mqttCheckType raises ValueError."""
        with self.assertRaises(ValueError):
            self.build(
                type=MonitorType.MQTT,
                name="test",
                hostname="broker.local",
                mqttCheckType="invalid-value",
            )

    def test_mqtt_websocket_path_too_long_raises(self):
        """mqttWebsocketPath exceeding 255 chars raises ValueError."""
        with self.assertRaises(ValueError):
            self.build(
                type=MonitorType.MQTT,
                name="test",
                hostname="broker.local",
                mqttWebsocketPath="x" * 256,
            )

    def test_mqtt_websocket_path_at_limit_ok(self):
        """mqttWebsocketPath at exactly 255 chars is valid."""
        result = self.build(
            type=MonitorType.MQTT,
            name="test",
            hostname="broker.local",
            mqttWebsocketPath="x" * 255,
        )
        self.assertEqual(result["mqttWebsocketPath"], "x" * 255)

    # ─── 7. Low-priority params version gate ──────────────────────────

    def test_low_priority_params_included_on_v2(self):
        """Low-priority params are included on v2 (not type-gated)."""
        result = self.build(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            subtype="http",
            wsSubprotocol="proto",
            wsIgnoreSecWebsocketAcceptHeader=True,
            remoteBrowsersToggle=True,
            remote_browser="chromium",
            screenshot_delay=1000,
            gamedigToken="tok",
            protocol="tcp",
        )
        self.assertEqual(result["subtype"], "http")
        self.assertEqual(result["wsSubprotocol"], "proto")
        self.assertTrue(result["wsIgnoreSecWebsocketAcceptHeader"])
        self.assertTrue(result["remoteBrowsersToggle"])
        self.assertEqual(result["remote_browser"], "chromium")
        self.assertEqual(result["screenshot_delay"], 1000)
        self.assertEqual(result["gamedigToken"], "tok")
        self.assertEqual(result["protocol"], "tcp")

    def test_low_priority_params_omitted_on_v1(self):
        """Low-priority params are omitted on v1."""
        build_v1 = self._build_v1()
        result = build_v1(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            subtype="http",
            wsSubprotocol="proto",
            remoteBrowsersToggle=True,
            screenshot_delay=500,
            gamedigToken="tok",
            protocol="udp",
        )
        self.assertNotIn("subtype", result)
        self.assertNotIn("wsSubprotocol", result)
        self.assertNotIn("remoteBrowsersToggle", result)
        self.assertNotIn("screenshot_delay", result)
        self.assertNotIn("gamedigToken", result)
        self.assertNotIn("protocol", result)

    def test_low_priority_params_none_omitted_on_v2(self):
        """Low-priority params left as None are not included on v2."""
        result = self.build(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            subtype=None,
            wsSubprotocol=None,
        )
        self.assertNotIn("subtype", result)
        self.assertNotIn("wsSubprotocol", result)

    # ─── 8. bearer_token independent of authMethod ────────────────────

    def test_bearer_token_with_auth_method_none(self):
        """bearer_token works when authMethod is NONE."""
        result = self.build(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            authMethod=AuthMethod.NONE,
            bearer_token="my-token",
        )
        self.assertEqual(result["bearer_token"], "my-token")

    def test_bearer_token_with_auth_method_basic(self):
        """bearer_token works when authMethod is HTTP_BASIC."""
        result = self.build(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            authMethod=AuthMethod.HTTP_BASIC,
            basic_auth_user="user",
            basic_auth_pass="pass",
            bearer_token="my-token",
        )
        self.assertEqual(result["bearer_token"], "my-token")

    def test_bearer_token_with_auth_method_ntlm(self):
        """bearer_token works when authMethod is NTLM."""
        result = self.build(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            authMethod=AuthMethod.NTLM,
            bearer_token="my-token",
        )
        self.assertEqual(result["bearer_token"], "my-token")

    def test_bearer_token_with_auth_method_mtls(self):
        """bearer_token works when authMethod is MTLS."""
        result = self.build(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            authMethod=AuthMethod.MTLS,
            bearer_token="my-token",
        )
        self.assertEqual(result["bearer_token"], "my-token")

    def test_bearer_token_with_auth_method_oauth2(self):
        """bearer_token works when authMethod is OAUTH2_CC."""
        result = self.build(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            authMethod=AuthMethod.OAUTH2_CC,
            bearer_token="my-token",
        )
        self.assertEqual(result["bearer_token"], "my-token")

    def test_bearer_token_for_keyword_type(self):
        """bearer_token works for KEYWORD type on v2."""
        result = self.build(
            type=MonitorType.KEYWORD,
            name="test",
            url="http://example.com",
            keyword="up",
            bearer_token="tok",
        )
        self.assertEqual(result["bearer_token"], "tok")

    def test_bearer_token_for_json_query_type(self):
        """bearer_token works for JSON_QUERY type on v2."""
        result = self.build(
            type=MonitorType.JSON_QUERY,
            name="test",
            url="http://example.com",
            jsonPath="$.ok",
            expectedValue="true",
            bearer_token="tok",
        )
        self.assertEqual(result["bearer_token"], "tok")


if __name__ == "__main__":
    unittest.main()
