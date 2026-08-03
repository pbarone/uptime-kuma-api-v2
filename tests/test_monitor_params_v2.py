"""
Unit tests for new monitor parameters in _build_monitor_data.

These tests mock the API version and call _build_monitor_data directly
without connecting to a live server.
"""
import random
import unittest
from unittest.mock import MagicMock

from packaging.version import InvalidVersion, parse as parse_version

from uptime_kuma_api import (
    MonitorType,
    AuthMethod,
    Event,
    MonitorBuilder,
    UptimeKumaException,
)
from uptime_kuma_api.api import UptimeKumaApi


class TestMonitorParamsV2(unittest.TestCase):
    """Tests for v2 monitor parameter handling in _build_monitor_data."""

    def setUp(self):
        self.api = MagicMock(spec=UptimeKumaApi)
        self.api.version = "2.4.0"
        # the real version-gate choke point, so gates parse self.version for real
        self.api._parsed_version = UptimeKumaApi._parsed_version.__get__(self.api)
        self.build = UptimeKumaApi._build_monitor_data.__get__(self.api)

    def _build_v1(self):
        """Return a _build_monitor_data bound to a v1 mock."""
        api = MagicMock(spec=UptimeKumaApi)
        api.version = "1.23.2"
        api._parsed_version = UptimeKumaApi._parsed_version.__get__(api)
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


TAG_ID = 1
MONITOR_ID = 7
TAG_VALUE = "test"
MONITOR_SNAPSHOT = {"id": MONITOR_ID, "name": "monitor 7"}


class TestMonitorTagCacheBugCondition(unittest.TestCase):
    """Bug C (#68) — monitor-list cache write crash on a ``None`` cache.

    Bug condition::

        isBugCondition_C(op, cacheState) == cacheState[MONITOR_LIST] is None

    Both ``add_monitor_tag`` and ``delete_monitor_tag`` patch the cached monitor
    list after the server call, because the ``monitorList`` event does not carry
    updated tags::

        self._event_data[Event.MONITOR_LIST][str(monitor_id)] = self.get_monitor(monitor_id)

    ``_event_data[Event.MONITOR_LIST]`` is initialised to ``None`` in
    ``__init__`` and only populated by the ``monitorList`` event, so on a
    session where that event has not landed the item assignment targets ``None``.
    ``add_status_page`` already guards the mirror case; these two methods do not.

    Unit tests: no live server. ``_call``, ``get_monitor``, ``get_monitors`` and
    ``wait_for_event`` are mocked and the real unbound method is bound to the
    mock instance, so only the cache-write behavior is under test.

    Property 5 (Bug Condition): with a ``None`` cache, neither operation may
    raise ``TypeError``.

    **Validates: Requirements 1.5, 2.6**
    """

    def _api_with_none_cache(self):
        api = MagicMock(spec=UptimeKumaApi)
        api._event_data = {Event.MONITOR_LIST: None}
        api._call.return_value = {"msg": "ok"}
        api.get_monitor.return_value = MONITOR_SNAPSHOT
        # delete_monitor_tag's tag-existence guard reads the monitor list
        api.get_monitors.return_value = [
            {
                "id": MONITOR_ID,
                "tags": [
                    {"monitor_id": MONITOR_ID, "tag_id": TAG_ID, "value": TAG_VALUE}
                ],
            }
        ]
        return api

    def test_add_monitor_tag_does_not_raise_when_cache_is_none(self):
        """add_monitor_tag with _event_data[MONITOR_LIST] = None must not raise."""
        api = self._api_with_none_cache()
        add_monitor_tag = UptimeKumaApi.add_monitor_tag.__get__(api)

        try:
            result = add_monitor_tag(TAG_ID, MONITOR_ID, TAG_VALUE)
        except TypeError as e:
            self.fail(
                "add_monitor_tag raised TypeError with an uninitialised "
                f"monitor-list cache: {e}"
            )

        self.assertEqual(result, {"msg": "ok"})
        api._call.assert_called_once_with(
            "addMonitorTag", (TAG_ID, MONITOR_ID, TAG_VALUE)
        )
        self.assertEqual(
            api._event_data[Event.MONITOR_LIST],
            {str(MONITOR_ID): MONITOR_SNAPSHOT},
        )

    def test_delete_monitor_tag_does_not_raise_when_cache_is_none(self):
        """delete_monitor_tag with _event_data[MONITOR_LIST] = None must not raise."""
        api = self._api_with_none_cache()
        delete_monitor_tag = UptimeKumaApi.delete_monitor_tag.__get__(api)

        try:
            result = delete_monitor_tag(TAG_ID, MONITOR_ID, TAG_VALUE)
        except TypeError as e:
            self.fail(
                "delete_monitor_tag raised TypeError with an uninitialised "
                f"monitor-list cache: {e}"
            )

        self.assertEqual(result, {"msg": "ok"})
        api._call.assert_called_once_with(
            "deleteMonitorTag", (TAG_ID, MONITOR_ID, TAG_VALUE)
        )
        self.assertEqual(
            api._event_data[Event.MONITOR_LIST],
            {str(MONITOR_ID): MONITOR_SNAPSHOT},
        )


OTHER_MONITOR_ID = 99
OTHER_MONITOR_SNAPSHOT = {"id": OTHER_MONITOR_ID, "name": "monitor 99"}
STALE_MONITOR_SNAPSHOT = {"id": MONITOR_ID, "name": "monitor 7", "tags": []}


class TestMonitorTagCachePreservation(unittest.TestCase):
    """Bug C (#68) — preservation baseline for a populated monitor-list cache.

    Bug condition::

        isBugCondition_C(op, cacheState) == cacheState[MONITOR_LIST] is None

    These cases are the ``NOT isBugCondition_C`` side: the cache is already a
    dict, so ``F(X) = F'(X)`` must hold. The observed (UNFIXED) behavior encoded
    here is:

    * the server response from ``_call`` is returned unchanged;
    * the cache entry for the target monitor is written/overwritten with the
      fresh ``get_monitor(monitor_id)`` snapshot, keyed by ``str(monitor_id)``;
    * pre-existing entries for other monitors are left untouched (same object).

    The planned None-guard must not alter any of this.

    Property 6 (Preservation): populated cache behaves identically.

    **Validates: Requirements 3.5**
    """

    def _api_with_populated_cache(self, include_target=False):
        api = MagicMock(spec=UptimeKumaApi)
        cache = {str(OTHER_MONITOR_ID): OTHER_MONITOR_SNAPSHOT}
        if include_target:
            cache[str(MONITOR_ID)] = STALE_MONITOR_SNAPSHOT
        api._event_data = {Event.MONITOR_LIST: cache}
        api._call.return_value = {"msg": "ok"}
        api.get_monitor.return_value = MONITOR_SNAPSHOT
        # delete_monitor_tag's tag-existence guard reads the monitor list
        api.get_monitors.return_value = [
            {
                "id": MONITOR_ID,
                "tags": [
                    {"monitor_id": MONITOR_ID, "tag_id": TAG_ID, "value": TAG_VALUE}
                ],
            }
        ]
        return api

    def _assert_cache_updated(self, api):
        cache = api._event_data[Event.MONITOR_LIST]
        self.assertEqual(cache[str(MONITOR_ID)], MONITOR_SNAPSHOT)
        # unrelated entry untouched, same object
        self.assertIs(cache[str(OTHER_MONITOR_ID)], OTHER_MONITOR_SNAPSHOT)
        self.assertEqual(
            set(cache), {str(MONITOR_ID), str(OTHER_MONITOR_ID)}
        )
        api.get_monitor.assert_called_once_with(MONITOR_ID)

    def test_add_monitor_tag_updates_populated_cache(self):
        """add_monitor_tag adds the fresh snapshot to an already populated cache."""
        api = self._api_with_populated_cache()
        add_monitor_tag = UptimeKumaApi.add_monitor_tag.__get__(api)

        result = add_monitor_tag(TAG_ID, MONITOR_ID, TAG_VALUE)

        self.assertEqual(result, {"msg": "ok"})
        api._call.assert_called_once_with(
            "addMonitorTag", (TAG_ID, MONITOR_ID, TAG_VALUE)
        )
        self._assert_cache_updated(api)

    def test_add_monitor_tag_overwrites_existing_cache_entry(self):
        """add_monitor_tag replaces a stale entry for the same monitor."""
        api = self._api_with_populated_cache(include_target=True)
        add_monitor_tag = UptimeKumaApi.add_monitor_tag.__get__(api)

        result = add_monitor_tag(TAG_ID, MONITOR_ID, TAG_VALUE)

        self.assertEqual(result, {"msg": "ok"})
        self._assert_cache_updated(api)

    def test_delete_monitor_tag_updates_populated_cache(self):
        """delete_monitor_tag refreshes the cache entry for an existing tag."""
        api = self._api_with_populated_cache(include_target=True)
        delete_monitor_tag = UptimeKumaApi.delete_monitor_tag.__get__(api)

        result = delete_monitor_tag(TAG_ID, MONITOR_ID, TAG_VALUE)

        self.assertEqual(result, {"msg": "ok"})
        api._call.assert_called_once_with(
            "deleteMonitorTag", (TAG_ID, MONITOR_ID, TAG_VALUE)
        )
        self._assert_cache_updated(api)

    def test_delete_monitor_tag_absent_tag_still_raises(self):
        """A tag that is not on the monitor still raises and sends no delete."""
        api = self._api_with_populated_cache(include_target=True)
        delete_monitor_tag = UptimeKumaApi.delete_monitor_tag.__get__(api)

        with self.assertRaises(UptimeKumaException):
            delete_monitor_tag(TAG_ID, MONITOR_ID, "not-the-stored-value")

        api._call.assert_not_called()
        cache = api._event_data[Event.MONITOR_LIST]
        self.assertIs(cache[str(MONITOR_ID)], STALE_MONITOR_SNAPSHOT)
        self.assertIs(cache[str(OTHER_MONITOR_ID)], OTHER_MONITOR_SNAPSHOT)


NIGHTLY_VERSION = "2.0.0-dev-nightly-20240101"
GARBAGE_VERSION = "not-a-version"

# Every gate constant that api.py compares self.version against.
GATE_CONSTANTS = ["1.22", "1.23", "1.23.1", "2.0"]


class _VersionOnlyApi(UptimeKumaApi):
    """A real ``UptimeKumaApi`` with only the server version wired up.

    ``__init__`` is deliberately not called (it would open a socket.io
    connection). ``_build_monitor_data`` touches no instance state other than
    ``self.version``, so overriding the ``version`` property is enough to drive
    every version gate offline.
    """

    def __init__(self, version):  # noqa: D107 - intentionally skips super()
        self._raw_version = version

    @property
    def version(self) -> str:
        return self._raw_version


class TestUnparseableVersionBugCondition(unittest.TestCase):
    """Bug D (#74) — non-PEP440 server versions crash every version gate.

    Bug condition::

        isBugCondition_D(X) == NOT isPep440Parseable(X)

    The ``version`` property returns the raw string the server reported, and
    roughly ten gate sites feed it straight into ``packaging.version.parse``::

        if parse_version(self.version) >= parse_version("1.22"):

    A nightly build string such as ``2.0.0-dev-nightly-20240101`` (and any other
    non-PEP440 string) makes ``parse_version`` raise ``InvalidVersion``, so every
    version-gated code path fails against such a server.

    The fix introduces a single private choke point, ``_parsed_version()``, which
    returns a max sentinel for unparseable input so an unknown/nightly version is
    treated as newest and all ``>=`` gates evaluate ``True``.

    Unit tests: no live server. A real ``UptimeKumaApi`` subclass supplies the
    raw version string via the ``version`` property; nothing else is mocked, so
    the gates run exactly as they do in production.

    Property 7 (Bug Condition): an unparseable version is treated as newest and
    never raises ``InvalidVersion``.

    **Validates: Requirements 1.6, 1.7, 2.7, 2.8**
    """

    def _assert_newest(self, raw_version):
        """The choke point must parse without raising and compare as newest."""
        api = _VersionOnlyApi(raw_version)

        try:
            parsed = api._parsed_version()
        except Exception as e:  # InvalidVersion pre-fix
            self.fail(
                f"_parsed_version() raised {type(e).__name__} for the "
                f"unparseable version {raw_version!r}: {e}"
            )

        for constant in GATE_CONSTANTS:
            self.assertTrue(
                parsed >= parse_version(constant),
                f"version {raw_version!r} did not compare as newest against "
                f"gate {constant!r}",
            )

    def test_parsed_version_nightly_is_newest(self):
        """A nightly build string parses to a newest-comparing value."""
        self._assert_newest(NIGHTLY_VERSION)

    def test_parsed_version_garbage_is_newest(self):
        """A garbage version string parses to a newest-comparing value."""
        self._assert_newest(GARBAGE_VERSION)

    def _assert_gated_path_runs(self, raw_version):
        """A version-gated code path must execute and take the newest branch."""
        api = _VersionOnlyApi(raw_version)

        try:
            result = api._build_monitor_data(
                type=MonitorType.HTTP,
                name="test",
                url="http://example.com",
                ipFamily="IPv4",
                cacheBust=True,
            )
        except Exception as e:  # InvalidVersion pre-fix
            self.fail(
                f"a version-gated path raised {type(e).__name__} for the "
                f"unparseable version {raw_version!r}: {e}"
            )

        # >= 1.22 gate
        self.assertIn("parent", result)
        # >= 1.23 gate
        self.assertIn("timeout", result)
        # >= 2.0 gates
        self.assertEqual(result["ipFamily"], "IPv4")
        self.assertTrue(result["cacheBust"])

    def test_gated_path_runs_for_nightly_version(self):
        """_build_monitor_data completes on a nightly version, newest branch taken."""
        self._assert_gated_path_runs(NIGHTLY_VERSION)

    def test_gated_path_runs_for_garbage_version(self):
        """_build_monitor_data completes on a garbage version, newest branch taken."""
        self._assert_gated_path_runs(GARBAGE_VERSION)


# The four canonical valid versions named in the preservation requirement:
# a pre-1.22 v1, a late v1, the v2 boundary itself, and a current v2.
CANONICAL_VALID_VERSIONS = ["1.17.0", "1.23.2", "2.0", "2.4.0"]

# PEP440-valid suffix forms, so the generated corpus exercises pre-releases,
# post-releases, dev-releases and local versions, not just plain triples.
PEP440_SUFFIXES = ["", "a1", "b2", "rc1", ".post1", ".dev0", "+local.1"]

# Seeded so a failure is reproducible; hypothesis is not a project dependency.
PBT_SEED = 20260101
PBT_CASES = 60


def generate_valid_pep440_versions(count=PBT_CASES, seed=PBT_SEED):
    """Generate valid PEP440 version strings around the v1/v2 gate boundary.

    The generator is constrained to the input space that matters: majors 1-2 and
    minors 0-30 straddle every gate constant the library compares against, so
    each generated case actually discriminates between the v1 and v2 branches
    instead of landing far outside the interesting range.

    Anything the generator produces is fed through ``parse_version`` and
    discarded if it does not parse, so the corpus can only ever contain the
    ``NOT isBugCondition_D`` (parseable) side of the domain.
    """
    rng = random.Random(seed)
    versions = list(CANONICAL_VALID_VERSIONS)
    while len(versions) < count:
        parts = [rng.randint(1, 2), rng.randint(0, 30)]
        if rng.random() < 0.6:
            parts.append(rng.randint(0, 9))
        raw = ".".join(str(p) for p in parts) + rng.choice(PEP440_SUFFIXES)
        try:
            parse_version(raw)
        except InvalidVersion:  # generator guard - keep the corpus valid-only
            continue
        versions.append(raw)
    return versions


class _GateProbeApi(_VersionOnlyApi):
    """``_VersionOnlyApi`` that captures ``_call`` instead of using a transport.

    Needed for the ``set_settings`` probe, which is the only offline-reachable
    site for the ``1.23`` / ``1.23.1`` gate pair.
    """

    def __init__(self, version):  # noqa: D107
        super().__init__(version)
        self.calls = []

    def _call(self, event, data=None):
        self.calls.append((event, data))
        return {"msg": "ok"}


class _RawVersionApi(UptimeKumaApi):
    """A real ``UptimeKumaApi`` with only ``info()`` wired up.

    Unlike ``_VersionOnlyApi`` this does NOT override the ``version`` property,
    so the real property implementation (``self.info().get("version")``) is the
    thing under test.
    """

    def __init__(self, version):  # noqa: D107 - intentionally skips super()
        self._raw_info = {"version": version, "latestVersion": "9.9.9"}

    def info(self) -> dict:
        return self._raw_info


class TestValidVersionGatePreservation(unittest.TestCase):
    """Bug D (#74) — preservation baseline for valid PEP440 server versions.

    Bug condition::

        isBugCondition_D(X) == NOT isPep440Parseable(X)

    These cases are the ``NOT isBugCondition_D`` side: the server reported a
    version string ``packaging`` can parse, so ``F(X) = F'(X)`` must hold. The
    planned fix routes every gate through a private ``_parsed_version()`` choke
    point; for a parseable version that accessor returns exactly
    ``parse_version(self.version)``, so nothing may move.

    The observed (UNFIXED) behavior encoded here, expressed through the two
    offline-reachable gate sites rather than the gate expression itself (so the
    baseline survives the refactor):

    * ``_build_monitor_data`` — ``parent`` appears from 1.22, ``timeout`` and
      ``invertKeyword`` from 1.23, ``ipFamily`` / ``cacheBust`` from 2.0;
    * ``set_settings`` — ``chromeExecutable`` appears from 1.23 and ``nscd``
      from 1.23.1;
    * the public ``version`` property returns the raw server string unchanged.

    Property 8 (Preservation): valid versions gate exactly as before, and
    ``version`` is still raw.

    **Validates: Requirements 3.6**
    """

    # ─── probes: each returns the observed {gate_constant: taken} ──────

    def _monitor_gates(self, raw_version):
        """Observed gate outcomes for ``_build_monitor_data``."""
        api = _GateProbeApi(raw_version)
        data = api._build_monitor_data(
            type=MonitorType.KEYWORD,
            name="test",
            url="http://example.com",
            keyword="up",
            parent=3,
            timeout=42,
            invertKeyword=True,
            ipFamily="IPv4",
            cacheBust=True,
        )
        return {
            "1.22": "parent" in data,
            "1.23": "timeout" in data and "invertKeyword" in data,
            "2.0": "ipFamily" in data and "cacheBust" in data,
        }

    def _settings_gates(self, raw_version):
        """Observed gate outcomes for ``set_settings``."""
        api = _GateProbeApi(raw_version)
        api.set_settings(chromeExecutable="/usr/bin/chromium", nscd=True)
        event, payload = api.calls[0]
        self.assertEqual(event, "setSettings")
        data = payload[0]
        return {
            "1.23": "chromeExecutable" in data,
            "1.23.1": "nscd" in data,
        }

    def _expected_gates(self, raw_version, constants):
        """The original expression: ``parse_version(self.version) >= X``."""
        parsed = parse_version(raw_version)
        return {c: parsed >= parse_version(c) for c in constants}

    # ─── 1. the four canonical versions gate as the original did ──────

    def test_monitor_gates_match_original_expression(self):
        """_build_monitor_data gates match parse_version(self.version) >= X."""
        for raw in CANONICAL_VALID_VERSIONS:
            with self.subTest(version=raw):
                observed = self._monitor_gates(raw)
                self.assertEqual(
                    observed, self._expected_gates(raw, observed), raw
                )

    def test_settings_gates_match_original_expression(self):
        """set_settings gates match parse_version(self.version) >= X."""
        for raw in CANONICAL_VALID_VERSIONS:
            with self.subTest(version=raw):
                observed = self._settings_gates(raw)
                self.assertEqual(
                    observed, self._expected_gates(raw, observed), raw
                )

    # ─── 2. the v1/v2 boundary, encoded literally ─────────────────────

    def test_v1_v2_boundary_is_preserved(self):
        """The concrete v1-vs-v2 branch taken by each canonical version."""
        expected = {
            # pre-1.22 v1: no parent, no timeout, no v2 fields
            "1.17.0": {"1.22": False, "1.23": False, "2.0": False},
            # late v1: parent + timeout, still no v2 fields
            "1.23.2": {"1.22": True, "1.23": True, "2.0": False},
            # the v2 boundary itself is inclusive
            "2.0": {"1.22": True, "1.23": True, "2.0": True},
            "2.4.0": {"1.22": True, "1.23": True, "2.0": True},
        }
        for raw, gates in expected.items():
            with self.subTest(version=raw):
                self.assertEqual(self._monitor_gates(raw), gates, raw)

    def test_settings_boundary_is_preserved(self):
        """The 1.23 / 1.23.1 settings gates for each canonical version."""
        expected = {
            "1.17.0": {"1.23": False, "1.23.1": False},
            "1.23.2": {"1.23": True, "1.23.1": True},
            "2.0": {"1.23": True, "1.23.1": True},
            "2.4.0": {"1.23": True, "1.23.1": True},
        }
        for raw, gates in expected.items():
            with self.subTest(version=raw):
                self.assertEqual(self._settings_gates(raw), gates, raw)

    # ─── 3. the public version property stays raw ─────────────────────

    def test_version_property_returns_raw_server_string(self):
        """version returns the server's string verbatim, parseable or not."""
        for raw in CANONICAL_VALID_VERSIONS + [NIGHTLY_VERSION, GARBAGE_VERSION]:
            with self.subTest(version=raw):
                api = _RawVersionApi(raw)
                self.assertEqual(api.version, raw)
                # identity: no normalisation, no re-formatting
                self.assertIs(api.version, raw)
                self.assertIsInstance(api.version, str)

    # ─── 4. PBT over generated valid PEP440 strings ───────────────────

    def test_generated_valid_versions_gate_as_original(self):
        """PBT: for every valid PEP440 version, observed gates == original gates.

        This is the durable form of the equivalence check: it compares the gate
        outcome actually taken by the version-gated code against the original
        ``parse_version(self.version) >= parse_version("X.Y")`` expression, so
        it holds both before and after the ``_parsed_version()`` refactor.
        """
        for raw in generate_valid_pep440_versions():
            with self.subTest(version=raw):
                monitor_observed = self._monitor_gates(raw)
                self.assertEqual(
                    monitor_observed,
                    self._expected_gates(raw, monitor_observed),
                    f"monitor gates moved for {raw!r}",
                )
                settings_observed = self._settings_gates(raw)
                self.assertEqual(
                    settings_observed,
                    self._expected_gates(raw, settings_observed),
                    f"settings gates moved for {raw!r}",
                )

    @unittest.skipUnless(
        hasattr(UptimeKumaApi, "_parsed_version"),
        "_parsed_version() does not exist yet (pre-fix)",
    )
    def test_generated_valid_versions_parsed_version_equivalence(self):
        """PBT: ``_parsed_version()`` equals ``parse_version(self.version)``.

        The choke point does not exist on the unfixed code, so this case is a
        skip pre-fix and becomes the direct Property 8 equivalence assertion
        once task 13.1 lands. The sibling test above covers the same property
        through the gate sites in both states, so nothing goes unchecked here.
        """
        for raw in generate_valid_pep440_versions():
            with self.subTest(version=raw):
                api = _VersionOnlyApi(raw)
                original = parse_version(raw)
                self.assertEqual(api._parsed_version(), original, raw)
                for constant in GATE_CONSTANTS:
                    self.assertEqual(
                        api._parsed_version() >= parse_version(constant),
                        original >= parse_version(constant),
                        f"gate {constant!r} moved for {raw!r}",
                    )


# The pre-2.0 server version every conditions-gate test is mocked against. Its
# literal form matters: requirement 2.3 wants the OBSERVED version in the error
# message, so the assertions below look for this exact string.
V1_VERSION = "1.23.2"

# A realistic Uptime Kuma 2.x conditions list. The library never validates the
# individual dicts (requirement 3.2), so the shape only has to be plausible.
SAMPLE_CONDITIONS = [
    {
        "type": "expression",
        "expression": {
            "variable": "record",
            "operator": "contains",
            "value": "1.1.1.1",
        },
    },
]


class TestConditionsV1Gate(unittest.TestCase):
    """The v2-only ``conditions`` field must not reach a pre-2.0 server.

    ``_build_monitor_data`` emits ``conditions`` from the unconditional common
    ``data`` dict, so every ``add_monitor()`` call against a 1.x server sends a
    column the v1 schema does not have and the insert is rejected with
    ``SQLITE_ERROR: table monitor has no column named conditions``. No caller
    opt-in is required -- the default path is enough.
    """

    def setUp(self):
        self.api = MagicMock(spec=UptimeKumaApi)
        self.api.version = "2.4.0"
        # the real version-gate choke point, so gates parse self.version for real
        self.api._parsed_version = UptimeKumaApi._parsed_version.__get__(self.api)
        # the real guard too -- a spec'd MagicMock would otherwise stub it out
        # and the version rejection would never run
        self.api._check_conditions_supported = (
            UptimeKumaApi._check_conditions_supported.__get__(self.api)
        )
        self.build = UptimeKumaApi._build_monitor_data.__get__(self.api)

    def _v1_api(self):
        """Return a MagicMock UptimeKumaApi reporting a pre-2.0 server version."""
        api = MagicMock(spec=UptimeKumaApi)
        api.version = V1_VERSION
        api._parsed_version = UptimeKumaApi._parsed_version.__get__(api)
        api._check_conditions_supported = (
            UptimeKumaApi._check_conditions_supported.__get__(api)
        )
        return api

    def _build_v1(self):
        """Return a _build_monitor_data bound to a v1 mock."""
        return UptimeKumaApi._build_monitor_data.__get__(self._v1_api())

    # ─── 1. implicit omission: no caller opt-in at all ────────────────

    def test_conditions_omitted_on_v1(self):
        """conditions is absent from a v1 payload when not supplied.

        This is the minimal, most direct encoding of the regression: the
        default ``add_monitor`` path against a 1.23.x server.

        **Validates: Requirements 2.1, 2.2**
        """
        result = self._build_v1()(
            type=MonitorType.HTTP,
            name="t",
            url="http://x",
        )
        self.assertNotIn("conditions", result)

    def test_conditions_omitted_on_v1_all_types(self):
        """conditions is absent on v1 for every monitor type, unconditionally.

        Direct evidence that the defect needs no opt-in and is not confined to
        one monitor type.

        **Validates: Requirements 2.1, 2.2**
        """
        cases = {
            MonitorType.HTTP: dict(url="http://x"),
            MonitorType.PING: dict(hostname="127.0.0.1"),
            MonitorType.PORT: dict(hostname="127.0.0.1", port=8080),
            MonitorType.DNS: dict(
                hostname="example.com",
                dns_resolve_server="1.1.1.1",
                port=53,
            ),
            MonitorType.KEYWORD: dict(url="http://x", keyword="ok"),
            MonitorType.PUSH: dict(),
        }
        for type_, kwargs in cases.items():
            with self.subTest(type=type_):
                result = self._build_v1()(type=type_, name="t", **kwargs)
                self.assertNotIn("conditions", result)

    # ─── 2. boundary: an explicit empty list is not a request ─────────

    def test_conditions_empty_list_omitted_on_v1(self):
        """conditions=[] on v1 raises nothing and emits no key.

        An explicit empty list is indistinguishable in effect from the default,
        so it is deliberately outside the bug condition: it is treated as "no
        conditions requested" and simply omitted rather than rejected. This is
        the case that pins the guard on truthiness rather than ``is not None``.

        **Validates: Requirements 2.1, 2.2**
        """
        result = self._build_v1()(
            type=MonitorType.HTTP,
            name="t",
            url="http://x",
            conditions=[],
        )
        self.assertNotIn("conditions", result)

    # ─── 3. explicit opt-in is rejected, never silently discarded ─────

    def _assert_names_all_three(self, message):
        """The message must name the field, the required version and the observed one.

        Requirement 2.3 asks for all three elements, so a message that only
        names the field is insufficient: a caller reading it has to be able to
        tell *which* server version is the problem and *what* is needed instead.
        """
        self.assertIn("conditions", message, message)
        self.assertIn("2.0", message, message)
        self.assertIn(V1_VERSION, message, message)

    def test_explicit_conditions_raises_on_v1(self):
        """An explicit conditions list on v1 raises UptimeKumaException.

        Silently dropping the field would produce a monitor that reports
        success against criteria the caller never set, so the field is rejected
        instead.

        **Validates: Requirements 2.3**
        """
        build = self._build_v1()

        with self.assertRaises(UptimeKumaException) as ctx:
            build(
                type=MonitorType.HTTP,
                name="t",
                url="http://x",
                conditions=SAMPLE_CONDITIONS,
            )

        self._assert_names_all_three(str(ctx.exception))

    def test_edit_monitor_explicit_conditions_raises_on_v1(self):
        """edit_monitor rejects an explicit conditions list before any server call.

        ``edit_monitor`` bypasses ``_build_monitor_data`` entirely -- it merges
        ``get_monitor(id_)`` output and calls ``editMonitor`` directly -- so it
        needs its own guard. Asserting that neither ``get_monitor`` nor
        ``_call`` was invoked is what proves the guard sits *ahead* of
        ``get_monitor(id_)``, which is requirement 2.3's "before any server call
        is made".

        **Validates: Requirements 2.5**
        """
        api = self._v1_api()
        api.get_monitor.return_value = {
            "id": 7,
            "type": MonitorType.HTTP,
            "name": "existing",
            "url": "http://x",
            "interval": 60,
            "maxretries": 0,
            "retryInterval": 60,
            "maxredirects": 10,
            "accepted_statuscodes": ["200-299"],
            "notificationIDList": [],
            "databaseConnectionString": None,
            # _check_arguments_monitor reads this unconditionally, so the mocked
            # server response has to carry it or the pre-fix run dies on a
            # KeyError before it can prove the guard is missing
            "dns_resolve_type": "A",
        }
        edit_monitor = UptimeKumaApi.edit_monitor.__get__(api)

        with self.assertRaises(UptimeKumaException) as ctx:
            edit_monitor(7, conditions=SAMPLE_CONDITIONS)

        self._assert_names_all_three(str(ctx.exception))
        api.get_monitor.assert_not_called()
        api._call.assert_not_called()

    def test_builder_conditions_raises_on_v1(self):
        """A MonitorBuilder-built config carrying conditions raises on v1.

        ``MonitorBuilder`` holds a plain dict with no server connection, so it
        is version-blind by design and cannot enforce this itself. Its output
        can only reach a server through ``add_monitor`` / ``edit_monitor``, so
        this test pins the enforcement boundary there rather than in the
        builder -- which is what lets the builder stay unchanged.

        **Validates: Requirements 2.4**
        """
        config = (
            MonitorBuilder()
            .type(MonitorType.HTTP)
            .name("t")
            .url("http://x")
            .conditions(SAMPLE_CONDITIONS)
            .build()
        )
        self.assertEqual(config["conditions"], SAMPLE_CONDITIONS)

        build = self._build_v1()

        with self.assertRaises(UptimeKumaException) as ctx:
            build(**config)

        self._assert_names_all_three(str(ctx.exception))


# The v1 HTTP default payload as OBSERVED against the unfixed code, with the
# `conditions` key removed. Every other key must survive the fix untouched
# (requirement 3.5), so this literal is the recorded pre-fix baseline rather
# than a hand-derived expectation.
V1_HTTP_DEFAULT_PAYLOAD_WITHOUT_CONDITIONS = {
    "type": MonitorType.HTTP,
    "name": "t",
    "interval": 60,
    "retryInterval": 60,
    "maxretries": 1,
    "notificationIDList": [],
    "upsideDown": False,
    "resendInterval": 0,
    "description": None,
    "httpBodyEncoding": "json",
    "parent": None,
    "url": "http://x",
    "maxredirects": 10,
    "accepted_statuscodes": ["200-299"],
    "expiryNotification": False,
    "ignoreTls": False,
    "proxyId": None,
    "method": "GET",
    "body": None,
    "headers": None,
    "authMethod": AuthMethod.NONE,
    "timeout": 48,
    "hostname": None,
    "packetSize": 56,
    "port": None,
    "dns_resolve_server": "1.1.1.1",
    "dns_resolve_type": "A",
    "mqttUsername": "",
    "mqttPassword": "",
    "mqttTopic": "",
    "mqttSuccessMessage": "",
    "databaseConnectionString": None,
}

# The monitor dict a mocked ``get_monitor`` hands back to ``edit_monitor``. It
# carries `dns_resolve_type` because ``_check_arguments_monitor`` reads that key
# unconditionally on the merge path.
EDIT_MONITOR_EXISTING = {
    "id": 7,
    "type": MonitorType.HTTP,
    "name": "existing",
    "url": "http://x",
    "interval": 60,
    "maxretries": 0,
    "retryInterval": 60,
    "maxredirects": 10,
    "accepted_statuscodes": ["200-299"],
    "notificationIDList": [],
    "databaseConnectionString": None,
    "dns_resolve_type": "A",
}

# The ``editMonitor`` payload as OBSERVED against the unfixed code for
# ``edit_monitor(7, interval=20)``, identical on both majors. Note
# ``notificationIDList`` arriving as ``{}``: ``_convert_monitor_input`` rewrites
# the list into a dict, and that conversion must keep happening (requirement
# 3.6), so the observed value is encoded rather than the input one.
EDIT_MONITOR_EXPECTED_PAYLOAD = {
    "id": 7,
    "type": MonitorType.HTTP,
    "name": "existing",
    "url": "http://x",
    "interval": 20,
    "maxretries": 0,
    "retryInterval": 60,
    "maxredirects": 10,
    "accepted_statuscodes": ["200-299"],
    "notificationIDList": {},
    "databaseConnectionString": None,
    "dns_resolve_type": "A",
}


class TestConditionsPreservation(unittest.TestCase):
    """Preservation baseline for the ``conditions`` v1 gate.

    Everything here holds on the UNFIXED code and must keep holding after the
    gate lands: v2 payloads byte-identical (Property 3), non-``conditions``
    behaviour unchanged on both majors (Property 4), and type validation still
    ahead of version handling (Property 5).

    Recorded observation-first -- each expectation was read off a real run
    against the unfixed code, not derived from the design -- so a later
    divergence means the fix moved something it should not have.
    """

    def setUp(self):
        self.api = MagicMock(spec=UptimeKumaApi)
        self.api.version = "2.4.0"
        self.api._parsed_version = UptimeKumaApi._parsed_version.__get__(self.api)
        # bind the real guard as well, otherwise the spec'd MagicMock stubs it
        # and the TypeError-ordering proof below would never reach it
        self.api._check_conditions_supported = (
            UptimeKumaApi._check_conditions_supported.__get__(self.api)
        )
        self.build = UptimeKumaApi._build_monitor_data.__get__(self.api)

    def _api_for(self, version):
        """Return a MagicMock UptimeKumaApi reporting the given server version."""
        api = MagicMock(spec=UptimeKumaApi)
        api.version = version
        api._parsed_version = UptimeKumaApi._parsed_version.__get__(api)
        api._check_conditions_supported = (
            UptimeKumaApi._check_conditions_supported.__get__(api)
        )
        return api

    def _build_for(self, version):
        """Return a _build_monitor_data bound to a mock of the given version."""
        return UptimeKumaApi._build_monitor_data.__get__(self._api_for(version))

    # ─── 1-3. v2 payloads byte-identical ──────────────────────────────

    def test_conditions_default_empty_list_on_v2(self):
        """conditions defaults to [] on v2 when the argument is absent.

        **Validates: Requirements 3.1**
        """
        result = self.build(type=MonitorType.HTTP, name="t", url="http://x")
        self.assertIn("conditions", result)
        self.assertEqual(result["conditions"], [])

    def test_conditions_explicit_list_passed_through_by_identity_on_v2(self):
        """An explicit list reaches the payload as the caller's own object.

        ``assertIs`` rather than ``assertEqual`` is the point: it pins the
        no-reallocation rule that is otherwise only stated in prose, so a future
        switch to ``conditions if conditions else list()`` fails a test instead
        of passing review. No individual condition dict is validated.

        **Validates: Requirements 3.2**
        """
        passed = [dict(c) for c in SAMPLE_CONDITIONS]

        result = self.build(
            type=MonitorType.HTTP,
            name="t",
            url="http://x",
            conditions=passed,
        )

        self.assertIs(result["conditions"], passed)

    def test_conditions_explicit_empty_list_identity_on_v2(self):
        """conditions=[] on v2 yields the caller's own empty list, not a fresh one.

        The ``is not None`` form preserves an intentional ``[]``; the rejected
        truthiness form would silently swap in a new object here.

        **Validates: Requirements 3.2**
        """
        passed = []

        result = self.build(
            type=MonitorType.HTTP,
            name="t",
            url="http://x",
            conditions=passed,
        )

        self.assertIs(result["conditions"], passed)

    # ─── 4. TypeError still precedes any version handling ─────────────

    def test_non_list_conditions_raises_type_error_on_both_majors(self):
        """A non-list conditions value raises TypeError first, on both majors.

        This is the ordering proof: on v1 the failure must be ``TypeError``,
        **not** ``UptimeKumaException``. It is the one case that catches a
        version guard being placed above the ``isinstance`` check, in which case
        a bad type on v1 would surface as a version complaint instead.

        **Validates: Requirements 3.3**
        """
        for version in ("2.4.0", V1_VERSION):
            build = self._build_for(version)
            for bad in ("not a list", {}):
                with self.subTest(version=version, conditions=bad):
                    with self.assertRaises(TypeError) as ctx:
                        build(
                            type=MonitorType.HTTP,
                            name="t",
                            url="http://x",
                            conditions=bad,
                        )
                    self.assertEqual(
                        str(ctx.exception),
                        "conditions must be a list or None",
                    )
                    self.assertNotIsInstance(ctx.exception, UptimeKumaException)

    # ─── 5. every existing gate still at its own boundary ─────────────

    def _observed_gates(self, version):
        """Gate outcomes observed through the fields each gate emits."""
        data = self._build_for(version)(
            type=MonitorType.KEYWORD,
            name="t",
            url="http://x",
            keyword="up",
            parent=3,
            timeout=42,
            invertKeyword=True,
            ipFamily="IPv4",
            cacheBust=True,
        )
        return {
            "parent": "parent" in data,
            "timeout": "timeout" in data,
            "invertKeyword": "invertKeyword" in data,
            "ipFamily": "ipFamily" in data,
            "cacheBust": "cacheBust" in data,
        }

    def test_existing_version_gates_unmoved(self):
        """parent at 1.22, timeout/invertKeyword at 1.23, ipFamily/cacheBust at 2.0.

        Observed against the unfixed code. The relocation must not disturb any
        of these boundaries, and must not add or remove a gate.

        **Validates: Requirements 3.4**
        """
        expected = {
            "1.17.0": {
                "parent": False,
                "timeout": False,
                "invertKeyword": False,
                "ipFamily": False,
                "cacheBust": False,
            },
            "1.22": {
                "parent": True,
                "timeout": False,
                "invertKeyword": False,
                "ipFamily": False,
                "cacheBust": False,
            },
            V1_VERSION: {
                "parent": True,
                "timeout": True,
                "invertKeyword": True,
                "ipFamily": False,
                "cacheBust": False,
            },
            "2.0": {
                "parent": True,
                "timeout": True,
                "invertKeyword": True,
                "ipFamily": True,
                "cacheBust": True,
            },
            "2.4.0": {
                "parent": True,
                "timeout": True,
                "invertKeyword": True,
                "ipFamily": True,
                "cacheBust": True,
            },
        }
        for version, gates in expected.items():
            with self.subTest(version=version):
                self.assertEqual(self._observed_gates(version), gates, version)

    # ─── 6. the rest of the v1 payload is untouched ───────────────────

    def test_non_conditions_v1_payload_identical(self):
        """Every v1 field other than conditions matches the pre-fix payload.

        Compared as a whole dict rather than key by key, so a field silently
        added or dropped by the relocation shows up here.

        **Validates: Requirements 3.5**
        """
        result = self._build_for(V1_VERSION)(
            type=MonitorType.HTTP,
            name="t",
            url="http://x",
        )
        result.pop("conditions", None)

        self.assertEqual(result, V1_HTTP_DEFAULT_PAYLOAD_WITHOUT_CONDITIONS)

    # ─── 7. edit_monitor's merge path is not disturbed ────────────────

    def test_edit_monitor_merge_path_unchanged_on_both_majors(self):
        """edit_monitor(id_, interval=20) merges and calls exactly as before.

        ``edit_monitor`` never calls ``_build_monitor_data``: it merges
        ``get_monitor(id_)`` output with the kwargs and calls ``editMonitor``
        directly. With no ``conditions`` kwarg the new guard must not interfere
        on either major -- same single ``get_monitor(7)``, same ``editMonitor``
        event, same payload.

        **Validates: Requirements 3.6**
        """
        for version in ("2.4.0", V1_VERSION):
            with self.subTest(version=version):
                api = self._api_for(version)
                api.get_monitor.return_value = dict(EDIT_MONITOR_EXISTING)
                api._call.return_value = {"monitorID": 7, "msg": "Saved."}
                edit_monitor = UptimeKumaApi.edit_monitor.__get__(api)

                result = edit_monitor(7, interval=20)

                self.assertEqual(result, {"monitorID": 7, "msg": "Saved."})
                api.get_monitor.assert_called_once_with(7)
                api._call.assert_called_once_with(
                    "editMonitor", EDIT_MONITOR_EXPECTED_PAYLOAD
                )
                event, payload = api._call.call_args[0]
                self.assertEqual(event, "editMonitor")
                self.assertNotIn("conditions", payload)

    # ─── 8. MonitorBuilder is version-blind and unchanged ─────────────

    def test_monitor_builder_unchanged(self):
        """conditions() returns self and build() emits only explicitly-set fields.

        The builder holds a plain dict with no server connection, so its output
        cannot vary with the server version -- which is exactly why enforcement
        lives at the ``add_monitor`` / ``edit_monitor`` boundary and the builder
        needs no change at all.

        **Validates: Requirements 3.7**
        """
        builder = MonitorBuilder()
        self.assertIs(builder.conditions(SAMPLE_CONDITIONS), builder)

        config = (
            MonitorBuilder()
            .type(MonitorType.HTTP)
            .name("t")
            .url("http://x")
            .conditions(SAMPLE_CONDITIONS)
            .build()
        )
        self.assertEqual(
            config,
            {
                "type": MonitorType.HTTP,
                "name": "t",
                "url": "http://x",
                "conditions": SAMPLE_CONDITIONS,
            },
        )

        # unset fields stay absent
        without = MonitorBuilder().type(MonitorType.HTTP).name("t").build()
        self.assertNotIn("conditions", without)

        # build() output is identical regardless of the server version, because
        # the builder has no connection and therefore no version knowledge
        for version in ("2.4.0", V1_VERSION):
            with self.subTest(version=version):
                self._api_for(version)  # a live client changes nothing here
                repeat = (
                    MonitorBuilder()
                    .type(MonitorType.HTTP)
                    .name("t")
                    .url("http://x")
                    .conditions(SAMPLE_CONDITIONS)
                    .build()
                )
                self.assertEqual(repeat, config)


# The seven adjacent v2-only fields from requirement 1.6, each with the monitor
# type whose block emits it and the minimum sibling arguments that block needs.
# ``_build_monitor_data`` does not run ``_check_arguments_monitor`` (``add_monitor``
# does), so these bases only have to satisfy the type-specific block itself.
ADJACENT_V2_FIELDS = [
    (
        "jsonPathOperator",
        "contains",
        MonitorType.JSON_QUERY,
        {"name": "t", "url": "http://x", "jsonPath": "$.status", "expectedValue": "ok"},
    ),
    (
        "snmp_v3_username",
        "snmpuser",
        MonitorType.SNMP,
        {"name": "t", "hostname": "h", "snmpOid": "1.3.6.1"},
    ),
    ("ping_count", 5, MonitorType.PING, {"name": "t", "hostname": "127.0.0.1"}),
    ("ping_numeric", True, MonitorType.PING, {"name": "t", "hostname": "127.0.0.1"}),
    (
        "ping_per_request_timeout",
        10,
        MonitorType.PING,
        {"name": "t", "hostname": "127.0.0.1"},
    ),
    (
        "mqttWebsocketPath",
        "/ws",
        MonitorType.MQTT,
        {"name": "t", "hostname": "broker.local", "port": 1883, "mqttTopic": "topic"},
    ),
    (
        "mqttCheckType",
        "keyword",
        MonitorType.MQTT,
        {"name": "t", "hostname": "broker.local", "port": 1883, "mqttTopic": "topic"},
    ),
]


class TestAdjacentV2FieldsPreservation(unittest.TestCase):
    """The seven adjacent v2-only fields are gated without new errors.

    Property 6. These fields sit in type-specific blocks outside the ``>= 2.0``
    block and are explicit-opt-in only, so the ratified policy for them is
    **silent omission on v1, no raise** -- unlike ``conditions``, which raises.

    The absence of a raise is asserted explicitly rather than left implicit, so a
    later change that starts raising for one of these fails a test instead of
    passing unnoticed. That negative assertion is the executable form of the
    policy decision.
    """

    def _api_for(self, version):
        """Return a MagicMock UptimeKumaApi reporting the given server version."""
        api = MagicMock(spec=UptimeKumaApi)
        api.version = version
        api._parsed_version = UptimeKumaApi._parsed_version.__get__(api)
        # MagicMock(spec=...) auto-stubs the guard, so bind the real one too --
        # otherwise a stubbed no-op would hide a misplaced conditions check
        api._check_conditions_supported = (
            UptimeKumaApi._check_conditions_supported.__get__(api)
        )
        return api

    def _build_for(self, version):
        """Return a _build_monitor_data bound to a mock of the given version."""
        return UptimeKumaApi._build_monitor_data.__get__(self._api_for(version))

    # ─── 1. absent on v1, present on v2 ───────────────────────────────

    def test_adjacent_fields_absent_from_v1_payload(self):
        """Each of the seven is omitted on v1 even when supplied explicitly.

        **Validates: Requirements 2.6**
        """
        build = self._build_for(V1_VERSION)
        for field, value, mtype, base in ADJACENT_V2_FIELDS:
            with self.subTest(field=field, version=V1_VERSION):
                result = build(type=mtype, **base, **{field: value})
                self.assertNotIn(field, result)

    def test_adjacent_fields_present_on_v2_exactly_as_before(self):
        """Each of the seven still reaches the v2 payload with its own value.

        The v2 side is the preservation half of the property: gating in place
        must not change what a 2.x server receives.

        **Validates: Requirements 3.5**
        """
        build = self._build_for("2.4.0")
        for field, value, mtype, base in ADJACENT_V2_FIELDS:
            with self.subTest(field=field, version="2.4.0"):
                result = build(type=mtype, **base, **{field: value})
                self.assertIn(field, result)
                self.assertEqual(result[field], value)

    # ─── 2. the explicit no-raise assertion ───────────────────────────

    def test_adjacent_fields_raise_nothing_on_v1(self):
        """Supplying any of the seven on v1 raises nothing at all.

        Deliberately catches bare ``Exception`` and fails with the field name:
        the point is that *no* error of any kind appears here, not merely that
        ``UptimeKumaException`` does not. Silent omission is the ratified policy
        for these seven, and this is where a future raise would be caught.

        **Validates: Requirements 2.6**
        """
        build = self._build_for(V1_VERSION)
        for field, value, mtype, base in ADJACENT_V2_FIELDS:
            with self.subTest(field=field, version=V1_VERSION):
                try:
                    build(type=mtype, **base, **{field: value})
                except Exception as exc:  # noqa: BLE001 - the assertion IS "nothing"
                    self.fail(
                        f"{field} on {V1_VERSION} raised "
                        f"{type(exc).__name__}: {exc}"
                    )

    def test_all_seven_together_on_v1_absent_and_silent(self):
        """All seven at once, per type, are dropped on v1 without raising.

        A per-field loop would miss an interaction between two gates in the same
        block (the three PING fields and the two MQTT fields share one nested
        gate each), so the fields are also supplied together here.

        **Validates: Requirements 2.6, 3.5**
        """
        build = self._build_for(V1_VERSION)
        all_fields = {field: value for field, value, _, _ in ADJACENT_V2_FIELDS}
        by_type = {}
        for field, value, mtype, base in ADJACENT_V2_FIELDS:
            by_type.setdefault(mtype, {}).update(base)

        for mtype, base in by_type.items():
            with self.subTest(type=mtype):
                try:
                    result = build(type=mtype, **base, **all_fields)
                except Exception as exc:  # noqa: BLE001 - the assertion IS "nothing"
                    self.fail(
                        f"all seven on {V1_VERSION} for {mtype} raised "
                        f"{type(exc).__name__}: {exc}"
                    )
                for field in all_fields:
                    self.assertNotIn(field, result)

    # ─── 3. argument validation still fires on both majors ────────────

    def test_mqtt_check_type_invalid_raises_value_error_on_both_majors(self):
        """An invalid mqttCheckType is a ValueError regardless of server version.

        The ``ValueError`` checks are argument validation, not payload emission:
        a bad value is bad on either major, so gating them would be a silent
        relaxation. They must keep firing on v1 even though the field itself is
        now dropped from the v1 payload.

        **Validates: Requirements 3.5**
        """
        for version in ("2.4.0", V1_VERSION):
            with self.subTest(version=version):
                with self.assertRaises(ValueError) as ctx:
                    self._build_for(version)(
                        type=MonitorType.MQTT,
                        name="t",
                        hostname="broker.local",
                        mqttCheckType="invalid-value",
                    )
                self.assertEqual(
                    str(ctx.exception),
                    "mqttCheckType must be 'keyword' or 'json-query', "
                    "got: invalid-value",
                )

    def test_mqtt_websocket_path_too_long_raises_value_error_on_both_majors(self):
        """An over-length mqttWebsocketPath is a ValueError on both majors.

        **Validates: Requirements 3.5**
        """
        for version in ("2.4.0", V1_VERSION):
            with self.subTest(version=version):
                with self.assertRaises(ValueError) as ctx:
                    self._build_for(version)(
                        type=MonitorType.MQTT,
                        name="t",
                        hostname="broker.local",
                        mqttWebsocketPath="x" * 256,
                    )
                self.assertEqual(
                    str(ctx.exception),
                    "mqttWebsocketPath must not exceed 255 characters",
                )

    def test_mqtt_valid_values_still_accepted_on_v1(self):
        """Valid mqtt values pass validation on v1 and are simply omitted.

        The boundary companion to the two ValueError cases: validation firing on
        v1 must not turn into validation *rejecting* a legal value there.

        **Validates: Requirements 2.6, 3.5**
        """
        build = self._build_for(V1_VERSION)
        for value in ("keyword", "json-query"):
            with self.subTest(mqttCheckType=value):
                result = build(
                    type=MonitorType.MQTT,
                    name="t",
                    hostname="broker.local",
                    mqttCheckType=value,
                    mqttWebsocketPath="x" * 255,
                )
                self.assertNotIn("mqttCheckType", result)
                self.assertNotIn("mqttWebsocketPath", result)


# ── Seeded generated-input corpora for the conditions gate ───────────
# Hypothesis is deliberately NOT a project dependency, so generation is a
# fixed-seed ``random.Random`` walk over a deliberately constrained input space,
# matching the ``generate_valid_pep440_versions`` idiom already in this file. A
# fixed seed keeps a CI failure reproducible and bisectable; the bounded case
# count keeps the suite fast.
CONDITIONS_PBT_SEED = 20260801
CONDITIONS_PBT_CASES = 48

# Sentinel for "the caller passed no ``conditions`` argument at all", which is
# the implicit sub-case of the bug condition and is distinct from an explicit
# ``conditions=[]``. A plain ``None`` would not do: ``conditions=None`` is an
# explicit argument that happens to be falsy.
CONDITIONS_ABSENT = object()

# Monitor types paired with the minimum sibling arguments their type-specific
# block needs. ``_build_monitor_data`` does not run ``_check_arguments_monitor``
# (``add_monitor`` does), so these bases only have to satisfy the block itself.
CONDITIONS_PBT_TYPE_BASES = [
    (MonitorType.HTTP, {"url": "http://x"}),
    (MonitorType.PING, {"hostname": "127.0.0.1"}),
    (MonitorType.PORT, {"hostname": "127.0.0.1", "port": 8080}),
    (
        MonitorType.DNS,
        {"hostname": "example.com", "dns_resolve_server": "1.1.1.1", "port": 53},
    ),
    (MonitorType.KEYWORD, {"url": "http://x", "keyword": "ok"}),
    (MonitorType.PUSH, {}),
    (
        MonitorType.JSON_QUERY,
        {"url": "http://x", "jsonPath": "$.status", "expectedValue": "ok"},
    ),
    (
        MonitorType.MQTT,
        {"hostname": "broker.local", "port": 1883, "mqttTopic": "topic"},
    ),
]

# Optional parameters mixed into the generated calls, each with values that are
# legal for the parameter. The point of varying them is Property 1's "any
# combination of other parameters" -- values that trip the preamble's own
# ``ValueError`` checks are excluded on purpose, because those cases are
# already covered directly and would only mask the conditions assertion here.
CONDITIONS_PBT_OPTIONAL_PARAMS = [
    ("interval", [20, 60, 300]),
    ("retryInterval", [30, 90]),
    ("maxretries", [0, 3]),
    ("upsideDown", [True, False]),
    ("resendInterval", [0, 10]),
    ("description", [None, "generated"]),
    ("parent", [None, 4]),
    ("timeout", [16, 48]),
    ("expiryNotification", [True, False]),
    ("ignoreTls", [True, False]),
    ("ipFamily", [None, "IPv4", "IPv6"]),
    ("cacheBust", [True, False]),
    ("responseMaxLength", [50, 1000]),
    ("accepted_statuscodes", [["200-299"], ["200", "301"]]),
]

CONDITION_VARIABLES = ["record", "status_code", "response_time", "body"]
CONDITION_OPERATORS = ["contains", "not_contains", "equals", "gt", "lt"]
CONDITION_VALUES = ["1.1.1.1", "200", "ok", "500", ""]


def generate_conditions_monitor_cases(
    count=CONDITIONS_PBT_CASES, seed=CONDITIONS_PBT_SEED
):
    """Generate ``(monitor_type, kwargs, conditions_arg)`` triples for the v1 gate.

    Every monitor type is emitted once with **no** ``conditions`` argument
    first, because the implicit sub-case is the whole regression: it fires with
    no caller opt-in whatsoever. The remaining cases are seeded-random
    combinations of type, optional parameters and one of the three
    ``conditions`` shapes that matter -- absent, an explicit empty list, and an
    explicit truthy list -- so the corpus straddles the guard's truthiness test
    rather than only one side of it.
    """
    rng = random.Random(seed)
    cases = [
        (mtype, dict(base), CONDITIONS_ABSENT)
        for mtype, base in CONDITIONS_PBT_TYPE_BASES
    ]
    while len(cases) < count:
        mtype, base = rng.choice(CONDITIONS_PBT_TYPE_BASES)
        kwargs = dict(base)
        chosen = rng.sample(
            CONDITIONS_PBT_OPTIONAL_PARAMS,
            rng.randint(0, min(4, len(CONDITIONS_PBT_OPTIONAL_PARAMS))),
        )
        for name, values in chosen:
            kwargs[name] = rng.choice(values)
        conditions_arg = rng.choice(
            [
                CONDITIONS_ABSENT,
                [],
                [_generate_condition(rng) for _ in range(rng.randint(1, 3))],
            ]
        )
        cases.append((mtype, kwargs, conditions_arg))
    return cases


def _generate_condition(rng):
    """One plausible Uptime Kuma 2.x condition dict.

    The library never validates individual condition dicts (requirement 3.2),
    so the shape only has to be plausible; what is being generated is variety,
    not validity.
    """
    condition = {
        "type": rng.choice(["expression", "group"]),
        "andOr": rng.choice(["and", "or"]),
        "expression": {
            "variable": rng.choice(CONDITION_VARIABLES),
            "operator": rng.choice(CONDITION_OPERATORS),
            "value": rng.choice(CONDITION_VALUES),
        },
    }
    if rng.random() < 0.3:
        condition["children"] = [
            {
                "type": "expression",
                "expression": {
                    "variable": rng.choice(CONDITION_VARIABLES),
                    "operator": rng.choice(CONDITION_OPERATORS),
                    "value": rng.choice(CONDITION_VALUES),
                },
            }
        ]
    return condition


def generate_condition_list_shapes(
    count=CONDITIONS_PBT_CASES, seed=CONDITIONS_PBT_SEED
):
    """Generate ``conditions`` list shapes for the v2 identity property.

    Starts from the two boundary shapes -- an explicit empty list and the
    canonical sample -- then adds seeded-random lists of one to four condition
    dicts, some with nested children.
    """
    rng = random.Random(seed)
    shapes = [[], [dict(c) for c in SAMPLE_CONDITIONS]]
    while len(shapes) < count:
        shapes.append(
            [_generate_condition(rng) for _ in range(rng.randint(1, 4))]
        )
    return shapes


class TestConditionsGeneratedInputs(unittest.TestCase):
    """Seeded generated-input tests for the ``conditions`` version gate.

    The ``FOR ALL input`` in Properties 1, 2 and 3 covers a domain far too wide
    to hand-enumerate: every server version, every monitor type, every
    combination of other parameters, every condition-list shape. These tests
    walk seeded slices of that domain instead of a few hand-picked points.

    ``subTest`` is used throughout so a generated counterexample is identifiable
    from the failure output alone -- with a fixed seed, the reported case is
    reproducible by re-running the same command.
    """

    def _api_for(self, version):
        """Return a MagicMock UptimeKumaApi reporting the given server version."""
        api = MagicMock(spec=UptimeKumaApi)
        api.version = version
        api._parsed_version = UptimeKumaApi._parsed_version.__get__(api)
        # MagicMock(spec=...) auto-stubs both of these; bind the real ones or a
        # stubbed no-op guard would silently pass every rejection assertion
        api._check_conditions_supported = (
            UptimeKumaApi._check_conditions_supported.__get__(api)
        )
        return api

    def _build_for(self, version):
        """Return a _build_monitor_data bound to a mock of the given version."""
        return UptimeKumaApi._build_monitor_data.__get__(self._api_for(version))

    # ─── 1. the version boundary, over generated PEP440 strings ───────

    def test_generated_versions_conditions_presence_matches_gate(self):
        """PBT: ``conditions`` is present iff the server is 2.0 or newer.

        The version-boundary form of Properties 1 and 3 in one assertion. The
        generated corpus carries pre-releases, post-releases, dev-releases and
        local versions around the boundary (``2.0rc1``, ``1.30.9``,
        ``2.0+local.1``, ...), not just plain triples, so an off-by-one in the
        comparison shows up as a counterexample rather than passing on the four
        canonical versions.

        **Validates: Requirements 2.1, 2.2, 3.1**
        """
        for raw in generate_valid_pep440_versions():
            with self.subTest(version=raw):
                result = self._build_for(raw)(
                    type=MonitorType.HTTP,
                    name="t",
                    url="http://x",
                )
                expected = parse_version(raw) >= parse_version("2.0")
                self.assertEqual(
                    "conditions" in result,
                    expected,
                    f"conditions presence wrong for {raw!r}: "
                    f"expected present={expected}, payload key "
                    f"{'present' if 'conditions' in result else 'absent'}",
                )
                if expected:
                    # the v2 default is preserved, not merely emitted
                    self.assertEqual(result["conditions"], [], raw)

    def test_generated_versions_explicit_conditions_gate_at_boundary(self):
        """PBT: an explicit list raises below 2.0 and passes through at or above it.

        The same boundary walked with the explicit sub-case, so the raise and
        the passthrough are pinned to the identical version predicate as the
        implicit case above. Below the boundary the message must still name all
        three required elements, including the generated observed version.

        **Validates: Requirements 2.3, 3.2**
        """
        for raw in generate_valid_pep440_versions():
            with self.subTest(version=raw):
                build = self._build_for(raw)
                passed = [dict(c) for c in SAMPLE_CONDITIONS]

                if parse_version(raw) >= parse_version("2.0"):
                    result = build(
                        type=MonitorType.HTTP,
                        name="t",
                        url="http://x",
                        conditions=passed,
                    )
                    self.assertIs(result["conditions"], passed, raw)
                    continue

                with self.assertRaises(UptimeKumaException) as ctx:
                    build(
                        type=MonitorType.HTTP,
                        name="t",
                        url="http://x",
                        conditions=passed,
                    )
                message = str(ctx.exception)
                self.assertIn("conditions", message, message)
                self.assertIn("2.0", message, message)
                self.assertIn(raw, message, message)

    # ─── 2. monitor type x parameter combinations on v1 ───────────────

    def test_generated_v1_cases_never_emit_conditions(self):
        """PBT: on v1, ``conditions`` never reaches the payload, for any input.

        Property 1's "any monitor type and any combination of other parameters"
        made executable: no generated case may put the unsupported column in a
        pre-2.0 payload, whether the argument was absent or an explicit empty
        list. Where a truthy list was supplied the rejection is asserted
        instead, so both halves of the guard's truthiness test are covered by
        the same corpus.

        The no-raise branch catches bare ``Exception`` deliberately: for an
        input outside the explicit sub-case the assertion is that *nothing* is
        raised, not merely that ``UptimeKumaException`` is not.

        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        build = self._build_for(V1_VERSION)
        for mtype, kwargs, conditions_arg in generate_conditions_monitor_cases():
            explicit = conditions_arg is not CONDITIONS_ABSENT
            with self.subTest(
                type=mtype,
                params=sorted(kwargs),
                conditions="absent" if not explicit else conditions_arg,
            ):
                call = dict(kwargs)
                if explicit:
                    call["conditions"] = conditions_arg

                if explicit and conditions_arg:
                    with self.assertRaises(UptimeKumaException) as ctx:
                        build(type=mtype, name="t", **call)
                    message = str(ctx.exception)
                    self.assertIn("conditions", message, message)
                    self.assertIn("2.0", message, message)
                    self.assertIn(V1_VERSION, message, message)
                    continue

                shown = repr(conditions_arg) if explicit else "absent"
                try:
                    result = build(type=mtype, name="t", **call)
                except Exception as exc:  # noqa: BLE001 - assertion IS "nothing"
                    self.fail(
                        f"{mtype} with {sorted(kwargs)} and conditions="
                        f"{shown} raised {type(exc).__name__}: {exc}"
                    )
                self.assertNotIn("conditions", result)

    # ─── 3. condition-list shapes on v2 keep caller identity ──────────

    def test_generated_condition_shapes_pass_through_by_identity_on_v2(self):
        """PBT: the emitted value is the same object the caller passed in.

        The no-reallocation property across generated shapes: empty lists,
        single conditions, multi-condition lists and nested-children forms all
        arrive in the payload as the caller's own object, with the nested dicts
        untouched too. This is what fails if the expression is ever changed to
        ``conditions if conditions else list()``, which allocates a fresh list
        and conflates ``None`` with ``[]``.

        **Validates: Requirements 3.1, 3.2**
        """
        build = self._build_for("2.4.0")
        for shape in generate_condition_list_shapes():
            with self.subTest(size=len(shape), conditions=shape):
                result = build(
                    type=MonitorType.HTTP,
                    name="t",
                    url="http://x",
                    conditions=shape,
                )
                self.assertIs(result["conditions"], shape)
                # no deep copy either: the nested dicts are the caller's own
                for index, condition in enumerate(shape):
                    self.assertIs(result["conditions"][index], condition)


if __name__ == "__main__":
    unittest.main()
