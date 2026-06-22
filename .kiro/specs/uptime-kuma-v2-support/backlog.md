# Backlog: Uptime Kuma v2 Full Support

Items to implement **after** basic v2 compatibility is shipped (conditions fix + status page fix).

Discovered via `build_inputs.py` diffing v1.23.16 vs v2.4.0 source.

---

## New Monitor Types

| Priority | Monitor Type | New Fields Required |
|----------|-------------|-------------------|
| Medium | RabbitMQ | `rabbitmqNodes`, `rabbitmqUsername`, `rabbitmqPassword` |
| Medium | SNMP | `snmpOid`, `snmpVersion`, `snmpV3Username` |
| Medium | SMTP | `smtpSecurity`, `expectedTlsAlert` |
| Low | System Service | `system_service_name` |

**Action**: Add new `MonitorType` enum values and corresponding parameters to `_build_monitor_data`.

---

## New Monitor Parameters (existing types)

| Priority | Field | Type | Applies To |
|----------|-------|------|-----------|
| High | `jsonPathOperator` | str | JSON_QUERY (currently only `==`, v2 adds more operators) |
| High | `ipFamily` | str | All network monitors (force IPv4/IPv6) |
| Medium | `cacheBust` | bool | HTTP (cache-busting query param) |
| Medium | `retryOnlyOnStatusCodeFailure` | bool | HTTP (smarter retry logic) |
| Medium | `bearer_token` | str | HTTP (Bearer auth — new auth method?) |
| Medium | `oauth_audience` | str | HTTP (OAuth audience parameter) |
| Medium | `domainExpiryNotification` | bool | HTTP (domain expiry separate from cert) |
| Medium | `saveResponse` | bool | HTTP (save full response body) |
| Medium | `saveErrorResponse` | bool | HTTP (save error responses) |
| Medium | `responseMaxLength` | int | HTTP (cap saved response size) |
| Medium | `responsecheck` | str | HTTP (response body checking) |
| Medium | `ping_count` | int | PING (multiple pings per check) |
| Medium | `ping_numeric` | bool | PING (numeric output) |
| Medium | `ping_per_request_timeout` | int | PING (per-request timeout) |
| Medium | `mqttWebsocketPath` | str | MQTT (websocket transport path) |
| Medium | `mqttCheckType` | str | MQTT (check mode) |
| Low | `subtype` | str | SSH/Websocket subtypes |
| Low | `wsSubprotocol` | str | Websocket subprotocol |
| Low | `wsIgnoreSecWebsocketAcceptHeader` | bool | Websocket header handling |
| Low | `remoteBrowsersToggle` | bool | Real Browser (remote browser option) |
| Low | `remote_browser` | str | Real Browser (remote browser ID) |
| Low | `screenshot_delay` | int | Real Browser (delay before screenshot) |
| Low | `gamedigToken` | str | Gamedig (auth token) |
| Low | `protocol` | str | Protocol selection |
| Low | `location` | str | Monitor location (nightly only, not in stable yet) |

**Action**: Add each as an optional parameter to `_build_monitor_data` with `None` default.

---

## Removed Monitor Fields

| Field | Notes |
|-------|-------|
| `grpcMetadata` | Removed from v2 UI. May still be accepted by server but no longer configurable via UI. Keep in library for backward compat, add deprecation note. |

---

## Status Page Changes

| Priority | Change | Details |
|----------|--------|---------|
| High | `googleAnalyticsId` replaced | v2 uses `analyticsType` + `analyticsId` + `analyticsScriptUrl` instead. Library still sends `googleAnalyticsId` which v2 ignores. |
| Medium | `password` removed | Status page password protection removed in v2. Remove from `_build_status_page_data` when version >= 2.0. |
| Medium | `showOnlyLastHeartbeat` added | New display option for status pages. |
| Medium | `rssTitle` added | RSS feed title customization. |
| Low | `autoRefreshInterval` re-added to v2 config UI | Despite being removed from the server-side data structure initially, it appears in the v2 StatusPage.vue. Investigate if it's back or just UI-only. |

**Action**: Update `_build_status_page_data` signature and body.

---

## Notification Provider Updates

v2 added 3 new notification providers:
- Nextcloud Talk
- Brevo (formerly Sendinblue)
- Evolution API

**Action**: Run `build_notifications.py` against v2 source to discover new notification fields and add them to `notification_providers.py`.

---

## Other Enhancements

| Priority | Item | Details |
|----------|------|---------|
| High | MariaDB connection support | v2 supports MariaDB. Library should work regardless since it's a WebSocket client, not a DB client. Verify no assumptions about SQLite in library code. |
| Medium | New `MonitorType` enum values | Add any new types (RabbitMQ, SNMP, SMTP monitor, System Service, etc.) |
| Medium | Version detection | Consider detecting the Uptime Kuma version on connect and gating v2-only parameters behind `parse_version(self.version) >= parse_version("2.0")` |
| Low | LiquidJS template docs | Document that email notification templates now use LiquidJS syntax in v2 |
| Low | Badge API duration format | v2 changed badge endpoint duration format to require units (e.g., `24h`, `30d`). Not relevant to this library (badge API is HTTP, not WebSocket). |

---

## Reference: Upstream PR #86 (markus-seidl)

PR #86 (https://github.com/lucasheld/uptime-kuma-api/pull/86) by @markus-seidl adds many of the same v2 fields listed above. When implementing backlog items, cherry-pick or reference their implementation where applicable and credit @markus-seidl in commit messages.

**Useful to cherry-pick from PR #86:**
- 15 new monitor parameters (same fields listed in our "New Monitor Parameters" section)
- `logger` parameter for `UptimeKumaApi.__init__` (passes logger to socketio client for debugging)
- `MonitorBuilder` DTO class (380-line builder pattern for fluent monitor creation — optional ergonomics)

**Do NOT adopt from PR #86:**
- `get_monitors` refactor (changes event handling; author notes tests are "still flaky")
- `conditions if conditions else list()` logic (bug: replaces intentional `[]` with new list)

**PR #86 branch:** `pr-86` (fetched locally via `git fetch upstream refs/pull/86/head:pr-86`)

---

## Prioritization Guide

1. **Ship basic v2 compat first** (current scope: conditions + autoRefreshInterval) ✅ Done
2. **Then**: `jsonPathOperator`, `ipFamily`, status page analytics fields (reference PR #86, credit @markus-seidl)
3. **Then**: New monitor types — RabbitMQ, SNMP, SMTP (reference PR #86, credit @markus-seidl)
4. **Then**: `logger` param, `MonitorBuilder` DTO (from PR #86, credit @markus-seidl)
5. **Then**: Everything else based on user requests
