# Implementation Plan: Uptime Kuma v2 Support Backlog

## Overview

Implement the remaining Uptime Kuma v2 support features in the `uptime-kuma-api` Python library. The work is divided into: new monitor types, new monitor parameters (version-gated), status page changes, new notification providers, logger parameter, MonitorBuilder DTO, documentation, and testing. All implementations maintain backward compatibility with v1.x instances via `parse_version` gating.

Attribution: Credit @markus-seidl (PR #86) in commit messages for cherry-picked items (monitor params, logger, MonitorBuilder).

## Tasks

- [ ] 1. Add new MonitorType enum values
  - [ ] 1.1 Add RABBITMQ, SNMP, SMTP, SYSTEM_SERVICE to `monitor_type.py`
    - Add `RABBITMQ = "rabbitmq"`, `SNMP = "snmp"`, `SMTP = "smtp"`, `SYSTEM_SERVICE = "system-service"` to the MonitorType enum
    - Add docstrings for each new member
    - _Requirements: 1.1_

- [ ] 2. Implement new monitor parameters in `_build_monitor_data`
  - [ ] 2.1 Add new parameter signatures and input validations
    - Add all new parameters to `_build_monitor_data` signature: `jsonPathOperator`, `ipFamily`, HTTP params (`cacheBust`, `retryOnlyOnStatusCodeFailure`, `bearer_token`, `oauth_audience`, `domainExpiryNotification`, `saveResponse`, `saveErrorResponse`, `responseMaxLength`, `responsecheck`), PING params (`ping_count`, `ping_numeric`, `ping_per_request_timeout`), MQTT params (`mqttWebsocketPath`, `mqttCheckType`), low-priority params (`subtype`, `wsSubprotocol`, `wsIgnoreSecWebsocketAcceptHeader`, `remoteBrowsersToggle`, `remote_browser`, `screenshot_delay`, `gamedigToken`, `protocol`), RABBITMQ params (`rabbitmqNodes`, `rabbitmqUsername`, `rabbitmqPassword`), SNMP params (`snmpOid`, `snmpVersion`, `snmp_v3_username`), SMTP params (`smtpSecurity`), SYSTEM_SERVICE params (`system_service_name`)
    - Add validation checks at the top of method body: `responseMaxLength` range [1, 10_000_000], `mqttCheckType` must be in (None, "keyword", "json-query"), `mqttWebsocketPath` must not exceed 255 chars
    - _Requirements: 2.1, 3.1, 3.4, 4.1, 5.1, 5.3, 5.4, 6.1_

  - [ ] 2.2 Implement type-conditional payload assembly for new monitor types
    - Add RABBITMQ block: serialize `rabbitmqNodes` as JSON string, include `rabbitmqUsername`, `rabbitmqPassword`
    - Add SNMP block: include `snmpOid`, `snmpVersion`, `snmp_v3_username` (if non-None)
    - Add SMTP block: include `smtpSecurity`
    - Add SYSTEM_SERVICE block: include `system_service_name`
    - Update port defaults: SNMP → 161, SMTP → 25
    - Update JSON_QUERY block to include `jsonPathOperator` (if non-None)
    - Add PING-specific params block (if non-None)
    - Add MQTT new params block (`mqttWebsocketPath`, `mqttCheckType`, if non-None)
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 2.2, 2.3, 4.2, 4.3, 5.2_

  - [ ] 2.3 Implement v2 version-gated parameter inclusion
    - Add `if parse_version(self.version) >= parse_version("2.0"):` block at end of method
    - Inside v2 gate: include `ipFamily` for network-type monitors (if non-None)
    - Inside v2 gate: include HTTP params for HTTP-family types (if non-None)
    - Inside v2 gate: include low-priority params (if non-None), not type-gated
    - Ensure v2-only params are silently omitted for v1 connections
    - _Requirements: 2.4, 2.5, 2.6, 3.2, 3.3, 3.5, 6.2, 6.3, 13.2, 13.3, 13.4_

  - [ ] 2.4 Update `_check_arguments_monitor` with new type required fields
    - Add to `required_args_by_type`: `MonitorType.RABBITMQ: ["rabbitmqNodes"]`, `MonitorType.SNMP: ["hostname", "snmpOid"]`, `MonitorType.SMTP: ["hostname"]`, `MonitorType.SYSTEM_SERVICE: ["system_service_name"]`
    - _Requirements: 1.6, 1.7, 1.8_

  - [ ] 2.5 Remove dead code: clean up any orphaned references from the old `googleAnalyticsId`-only path in monitor/status page code
    - Verify no stale imports or unreachable branches remain after changes
    - _Requirements: (cleanup)_

- [ ] 3. Implement status page changes in `_build_status_page_data`
  - [ ] 3.1 Add new status page parameters and version-gated logic
    - Add parameters to signature: `analyticsType`, `analyticsId`, `analyticsScriptUrl`, `password`, `showOnlyLastHeartbeat`, `rssTitle`
    - In body: when version >= 2.0, include v2 analytics fields (if non-None), omit `googleAnalyticsId`, omit `password`, include `showOnlyLastHeartbeat` (if non-None), include `rssTitle` (if non-None)
    - In body: when version < 2.0, include `googleAnalyticsId`, include `password` (if non-None), omit v2 fields
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4_

  - [ ] 3.2 Update `save_status_page` to defensively pop v2-incompatible fields
    - Pop `googleAnalyticsId` from fetched status page data before passing to builder (v2 may not return it)
    - Ensure `showOnlyLastHeartbeat` and `rssTitle` pass through from fetched data
    - _Requirements: 7.6, 9.5_

- [ ] 4. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Add new notification providers
  - [ ] 5.1 Add Nextcloud Talk, Brevo, Evolution API to `notification_providers.py`
    - Add enum members: `NEXTCLOUD_TALK = "nextcloudtalk"`, `BREVO = "Brevo"`, `EVOLUTION_API = "evolution"` with docstrings
    - Add `notification_provider_options` entries with required/optional fields per provider as specified in design
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [ ] 6. Implement logger parameter
  - [ ] 6.1 Add `logger` parameter to `UptimeKumaApi.__init__`
    - Add `logger=None` to constructor signature
    - Add type validation: raise TypeError if not Logger, bool, or None
    - Build `sio_kwargs` dict, conditionally include `logger` key
    - Replace `socketio.Client(ssl_verify=ssl_verify)` with `socketio.Client(**sio_kwargs)`
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [ ] 7. Implement MonitorBuilder DTO
  - [ ] 7.1 Create `monitor_builder.py` with MonitorBuilder class
    - Create new file `uptime_kuma_api/monitor_builder.py`
    - Implement MonitorBuilder class with `__init__`, fluent setter methods for ALL `_build_monitor_data` parameters, and `build()` method
    - `build()` validates that `type` and `name` are set, raises ValueError if missing
    - Each setter returns `self` for chaining
    - Last-set-wins semantics for duplicate setter calls
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

  - [ ] 7.2 Export MonitorBuilder from `__init__.py`
    - Add `from .monitor_builder import MonitorBuilder` to `uptime_kuma_api/__init__.py`
    - _Requirements: 12.1_

- [ ] 8. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Write property-based tests (Hypothesis)
  - [ ]* 9.1 Write property test: new monitor type payload assembly
    - **Property 1: New monitor type payload assembly**
    - For any new monitor type (RABBITMQ, SNMP, SMTP, SYSTEM_SERVICE) with valid type-specific params, `_build_monitor_data` produces a dict containing those params unchanged
    - Use `@given(st.sampled_from([MonitorType.RABBITMQ, MonitorType.SNMP, MonitorType.SMTP, MonitorType.SYSTEM_SERVICE]))` + type-specific param strategies
    - File: `tests/test_properties.py`
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.5**

  - [ ]* 9.2 Write property test: jsonPathOperator conditional inclusion
    - **Property 2: jsonPathOperator conditional inclusion**
    - For any MonitorType and any non-None jsonPathOperator string, the key appears in output iff type is JSON_QUERY
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [ ]* 9.3 Write property test: ipFamily version-gated inclusion
    - **Property 3: ipFamily conditional inclusion with version gate**
    - For any MonitorType, non-None ipFamily, and server version: included iff type is network type AND version >= 2.0
    - **Validates: Requirements 2.4, 2.5, 2.6, 13.2, 13.3, 13.4**

  - [ ]* 9.4 Write property test: HTTP params version-gated inclusion
    - **Property 4: HTTP params conditional inclusion with version gate**
    - For HTTP-family types, version >= 2.0, subset of HTTP params: output contains exactly non-None params
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.5**

  - [ ]* 9.5 Write property test: responseMaxLength range validation
    - **Property 5: responseMaxLength range validation**
    - For any integer outside [1, 10_000_000], raises ValueError
    - **Validates: Requirements 3.4**

  - [ ]* 9.6 Write property test: bearer_token independence from authMethod
    - **Property 6: bearer_token independence from authMethod**
    - For any authMethod and non-None bearer_token, HTTP-family type + version >= 2.0 → output contains bearer_token
    - **Validates: Requirements 3.5**

  - [ ]* 9.7 Write property test: PING params conditional inclusion
    - **Property 7: PING params conditional inclusion**
    - For PING params subset, type PING → included; type not PING → absent
    - **Validates: Requirements 4.1, 4.2, 4.3**

  - [ ]* 9.8 Write property test: MQTT params validation
    - **Property 8: MQTT params conditional inclusion and validation**
    - Valid mqttWebsocketPath/mqttCheckType → included for MQTT type; invalid → ValueError
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

  - [ ]* 9.9 Write property test: low-priority params version gate
    - **Property 9: Low-priority params version-gated inclusion**
    - For low-priority params subset: version >= 2.0 → included; version < 2.0 → absent
    - **Validates: Requirements 6.1, 6.2, 6.3, 13.2, 13.3**

  - [ ]* 9.10 Write property test: status page version-gated field routing
    - **Property 10: Status page version-gated field routing**
    - For analytics/password/new fields: v2 → v2 fields present, v1 fields absent; v1 → v1 fields present, v2 fields absent
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.5, 9.2, 9.3, 9.4**

  - [ ]* 9.11 Write property test: logger type validation
    - **Property 11: Logger type validation**
    - For non-Logger, non-bool, non-None values → TypeError raised
    - **Validates: Requirements 11.4**

  - [ ]* 9.12 Write property test: MonitorBuilder setter chaining
    - **Property 12: MonitorBuilder setter chaining**
    - For any setter method and valid arg, calling setter returns same instance (identity)
    - **Validates: Requirements 12.2**

  - [ ]* 9.13 Write property test: MonitorBuilder build output
    - **Property 13: MonitorBuilder build contains exactly set fields**
    - For any subset of fields set (including type/name), build() returns dict with exactly those keys
    - **Validates: Requirements 12.3, 12.5**

- [ ] 10. Write unit tests
  - [ ]* 10.1 Write unit tests for new monitor types
    - Test each new type with all required fields → verify dict output shape
    - Test each new type with a required field missing → verify TypeError
    - Test port defaults (SNMP → 161, SMTP → 25)
    - File: `tests/test_monitor.py` (extend existing)
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [ ]* 10.2 Write unit tests for new monitor parameters
    - Test jsonPathOperator inclusion for JSON_QUERY type
    - Test jsonPathOperator exclusion for non-JSON_QUERY types
    - Test ipFamily inclusion/exclusion based on type and version
    - Test HTTP params included only for HTTP-family types on v2
    - Test responseMaxLength boundary values
    - Test PING/MQTT/low-priority param inclusion logic
    - File: `tests/test_monitor.py` (extend existing)
    - _Requirements: 2.1-2.6, 3.1-3.5, 4.1-4.3, 5.1-5.4, 6.1-6.3_

  - [ ]* 10.3 Write unit tests for status page changes
    - Test v2 analytics fields included, googleAnalyticsId omitted on v2
    - Test v1 googleAnalyticsId included, v2 analytics omitted on v1
    - Test password omitted on v2, included on v1
    - Test showOnlyLastHeartbeat and rssTitle included on v2, omitted on v1
    - Test save_status_page defensively pops googleAnalyticsId
    - File: `tests/test_status_page.py` (extend existing)
    - _Requirements: 7.1-7.6, 8.1-8.5, 9.1-9.5_

  - [ ]* 10.4 Write unit tests for notification providers
    - Test each new provider with all required fields → verify no validation error
    - Test each new provider with a required field missing → verify error raised
    - File: `tests/test_notification.py` (extend existing)
    - _Requirements: 10.1-10.6_

  - [ ]* 10.5 Write unit tests for logger parameter
    - Test Logger instance passes to socketio.Client
    - Test None omits logger from socketio kwargs
    - Test True (bool) accepted
    - Test invalid types (int, str, list) raise TypeError
    - File: `tests/test_monitor.py` or `tests/test_api.py`
    - _Requirements: 11.1-11.4_

  - [ ]* 10.6 Write unit tests for MonitorBuilder
    - Test fluent chaining returns same instance
    - Test build() with type+name → correct dict
    - Test build() without type → ValueError
    - Test build() without name → ValueError
    - Test last-set-wins for duplicate setter calls
    - Test build() output directly usable with `add_monitor(**builder.build())`
    - File: `tests/test_monitor_builder.py` (new file)
    - _Requirements: 12.1-12.6_

- [ ] 11. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Update documentation
  - [ ] 12.1 Update `docstrings.py` with new parameter documentation
    - Add docstrings for all new parameters in `_build_monitor_data`
    - Add docstrings for new status page parameters
    - Add docstrings for logger parameter
    - Document MonitorBuilder usage
    - _Requirements: (documentation)_

  - [ ] 12.2 Update `CHANGELOG.md`
    - Add entry under new version section for: new monitor types (RABBITMQ, SNMP, SMTP, SYSTEM_SERVICE), new monitor parameters, status page v2 analytics + password removal + new fields, new notification providers (Nextcloud Talk, Brevo, Evolution API), logger parameter, MonitorBuilder DTO, version detection improvements
    - Credit @markus-seidl (PR #86) in changelog
    - _Requirements: 14.1, 14.2, 14.3_

  - [ ] 12.3 Update `README.md`
    - Add MonitorBuilder usage example to README
    - Mention v2 support improvements
    - List new monitor types supported
    - _Requirements: (documentation)_

- [ ] 13. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Live environment integration test
  - [ ] 14.1 Test new features against user's live Uptime Kuma v2 instance
    - Connect to user's running Uptime Kuma v2 instance (not Docker)
    - Create a monitor of each new type (RABBITMQ, SNMP, SMTP, SYSTEM_SERVICE) with valid params → verify success
    - Create a notification with each new provider (Nextcloud Talk, Brevo, Evolution API) → verify success
    - Save a status page with v2 analytics fields → verify analytics fields round-trip correctly
    - Test MonitorBuilder output with `add_monitor(**builder.build())` → verify end-to-end
    - Verify ipFamily and HTTP params are accepted by v2 server
    - Clean up created test resources after verification
    - _Requirements: 1.7, 10.5, 7.1, 12.3, 13.4_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All v2-only features use `parse_version(self.version) >= parse_version("2.0")` gating
- Credit @markus-seidl (PR #86) in commit messages for monitor params, logger, and MonitorBuilder
- DO NOT adopt from PR #86: `get_monitors` refactor or `conditions if conditions else list()` pattern

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "5.1"] },
    { "id": 2, "tasks": ["2.2", "2.4", "6.1"] },
    { "id": 3, "tasks": ["2.3", "2.5", "7.1"] },
    { "id": 4, "tasks": ["3.1", "7.2"] },
    { "id": 5, "tasks": ["3.2"] },
    { "id": 6, "tasks": ["9.1", "9.2", "9.3", "9.4", "9.5", "9.6", "9.7", "9.8", "9.9", "9.10", "9.11", "9.12", "9.13"] },
    { "id": 7, "tasks": ["10.1", "10.2", "10.3", "10.4", "10.5", "10.6"] },
    { "id": 8, "tasks": ["12.1", "12.2", "12.3"] },
    { "id": 9, "tasks": ["14.1"] }
  ]
}
```
