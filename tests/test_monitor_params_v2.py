"""
Unit tests for new monitor parameters in _build_monitor_data.

These tests mock the API version and call _build_monitor_data directly
without connecting to a live server.
"""
import random
import unittest
from unittest.mock import MagicMock

from packaging.version import InvalidVersion, parse as parse_version

from uptime_kuma_api import MonitorType, AuthMethod, Event, UptimeKumaException
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


if __name__ == "__main__":
    unittest.main()
