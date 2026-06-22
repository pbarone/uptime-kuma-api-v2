# Requirements Document

## Introduction

Update the `uptime-kuma-api` Python library to support Uptime Kuma v2.x. The primary blocker is the required `conditions` column added to the monitor database table in v2, which causes `SQLITE_CONSTRAINT: NOT NULL constraint failed: monitor.conditions` errors when creating monitors through the API. Additionally, the `save_status_page` method fails on v2 due to a removed `autoRefreshInterval` field. This update incorporates fixes from upstream PRs #87 and #88, extends `conditions` support to all monitor types, and maintains backward compatibility with Uptime Kuma v1.x instances.

## Glossary

- **Library**: The `uptime-kuma-api` Python package that wraps the Uptime Kuma WebSocket API
- **Monitor**: An entity in Uptime Kuma that periodically checks the availability of a service or host
- **Conditions**: A JSON array field required by Uptime Kuma v2 on the monitor table, representing validation rules for monitor checks (e.g., expected DNS records, response content assertions)
- **Monitor_Builder**: The `_build_monitor_data` method in `api.py` that assembles the monitor payload sent to the server
- **Status_Page_Handler**: The `save_status_page` method in `api.py` that persists status page configuration
- **Uptime_Kuma_v1**: Uptime Kuma versions prior to 2.0.0
- **Uptime_Kuma_v2**: Uptime Kuma versions 2.0.0 and later

## Requirements

### Requirement 1: Conditions Field for All Monitor Types

**User Story:** As a developer using the library, I want to create monitors on Uptime Kuma v2 without encountering NOT NULL constraint errors, so that I can manage monitoring through the API on modern Uptime Kuma instances.

#### Acceptance Criteria

1. WHEN a monitor is created without an explicit `conditions` parameter, THE Monitor_Builder SHALL include a `conditions` field with an empty list value (`[]`) in the payload sent to the server
2. WHEN a monitor is created with an explicit `conditions` parameter containing a list of zero or more condition dictionaries, THE Monitor_Builder SHALL include the provided `conditions` list value unchanged in the payload
3. THE Library SHALL accept the `conditions` parameter for all monitor types including HTTP, PING, PORT, KEYWORD, DNS, DOCKER, PUSH, STEAM, GAMEDIG, MQTT, SQLSERVER, POSTGRES, MYSQL, MONGODB, RADIUS, REDIS, GROUP, JSON_QUERY, REAL_BROWSER, KAFKA_PRODUCER, GRPC_KEYWORD, and TAILSCALE_PING
4. WHEN the `conditions` parameter is set to None, THE Monitor_Builder SHALL convert it to an empty list (`[]`) in the payload
5. IF the `conditions` parameter is provided with a value that is not a list and not None, THEN THE Library SHALL raise a TypeError indicating that `conditions` must be a list or None

### Requirement 2: Backward Compatibility with Uptime Kuma v1

**User Story:** As a developer managing both v1 and v2 Uptime Kuma instances, I want the library to work with both versions, so that I do not need separate library versions per server.

#### Acceptance Criteria

1. WHEN connected to an Uptime Kuma v1 instance and `add_monitor` is called with valid monitor parameters, THE Library SHALL create the monitor and return a success response containing the new monitor ID
2. THE Library SHALL treat the `conditions` parameter as optional with a default value of an empty list for both `add_monitor` and `edit_monitor` operations
3. WHEN `edit_monitor` retrieves existing monitor data from a v1 instance that does not contain a `conditions` field, THE Library SHALL default the `conditions` field to an empty list before sending the update payload
4. WHEN editing an existing monitor on Uptime Kuma v1, THE Library SHALL include the `conditions` field in the payload and the v1 server SHALL accept the update without returning an error response

### Requirement 3: DNS Monitor Conditions

**User Story:** As a developer monitoring DNS records, I want to specify expected DNS record conditions, so that the monitor validates responses against my expectations.

#### Acceptance Criteria

1. WHEN a DNS monitor is created with a `conditions` parameter containing a list of condition objects, THE Monitor_Builder SHALL include those condition objects in the payload sent to the server
2. WHEN a DNS monitor is created without a `conditions` parameter, THE Monitor_Builder SHALL default to an empty list in the payload
3. THE Library SHALL accept condition objects as dictionaries containing the fields `type`, `variable`, `operator`, `value`, and `andOr`, where each field value is a string
4. WHEN a DNS monitor is created with a `conditions` list containing multiple condition objects, THE Monitor_Builder SHALL preserve the order and content of all condition objects in the payload
5. IF a condition object is provided with one or more of the required fields (`type`, `variable`, `operator`, `value`) set to None or missing, THEN THE Library SHALL pass the condition object through to the server without client-side rejection

### Requirement 4: Fix Status Page Save for v2

**User Story:** As a developer managing status pages on Uptime Kuma v2, I want `save_status_page` to succeed without KeyError exceptions, so that I can update status page configuration through the API.

#### Acceptance Criteria

1. WHEN saving a status page, THE Status_Page_Handler SHALL remove the `autoRefreshInterval` field from the data retrieved from the server before passing it to the internal build method
2. IF the `autoRefreshInterval` field is not present in the status page data retrieved from the server, THEN THE Status_Page_Handler SHALL proceed with the save operation and return a successful response without raising an exception
3. WHEN saving a status page after removing unsupported fields, THE Status_Page_Handler SHALL preserve all other status page configuration fields and return the server response containing the updated `publicGroupList`

### Requirement 5: Cherry-Pick and Integrate Upstream PRs

**User Story:** As a maintainer of the fork, I want to incorporate upstream PR #87 and #88 before adding further fixes, so that existing community work is preserved and attributed.

#### Acceptance Criteria

1. WHEN saving a status page, THE Library SHALL remove the `autoRefreshInterval` field from the status page data before sending the update to the server, consistent with the behavior introduced in upstream PR #87
2. WHEN a DNS monitor is created with a `conditions` parameter, THE Library SHALL include the `conditions` value in the monitor payload sent to the server, consistent with the behavior introduced in upstream PR #88
3. THE Library SHALL place the `conditions` field in the common monitor data section of the Monitor_Builder so that all monitor types include `conditions` in their payload, extending the DNS-only scope of upstream PR #88
4. THE Library SHALL preserve upstream PR author attribution in the git history through cherry-pick commits or merge commits that reference the original authors

### Requirement 6: Validate Monitor Creation on Uptime Kuma v2.4.0

**User Story:** As a developer, I want to verify that the key monitor types create successfully on a live v2.4.0 instance, so that I have confidence the fix resolves the reported issue.

#### Acceptance Criteria

1. WHEN `add_monitor` is called with `type=MonitorType.HTTP`, a `name` of at most 150 characters, and a `url` containing a reachable HTTP(s) endpoint, THE Library SHALL return a response containing `"msg": "Added Successfully."` and an integer `monitorID`, and the created monitor SHALL be retrievable via `get_monitor` using that `monitorID`
2. WHEN `add_monitor` is called with `type=MonitorType.PING`, a `name` of at most 150 characters, and a `hostname` containing a valid IPv4 address or resolvable domain name, THE Library SHALL return a response containing `"msg": "Added Successfully."` and an integer `monitorID`, and the created monitor SHALL be retrievable via `get_monitor` using that `monitorID`
3. WHEN `add_monitor` is called with `type=MonitorType.PORT`, a `name` of at most 150 characters, a `hostname` containing a valid IPv4 address or resolvable domain name, and a `port` between 0 and 65535, THE Library SHALL return a response containing `"msg": "Added Successfully."` and an integer `monitorID`, and the created monitor SHALL be retrievable via `get_monitor` using that `monitorID`
4. WHEN `add_monitor` is called with `type=MonitorType.DNS`, a `name` of at most 150 characters, a `hostname` containing a valid IPv4 address or resolvable domain name, a `port` between 0 and 65535, and a `dns_resolve_server` containing a valid IPv4 address of a DNS server, THE Library SHALL return a response containing `"msg": "Added Successfully."` and an integer `monitorID`, and the created monitor SHALL be retrievable via `get_monitor` using that `monitorID`
5. WHEN `add_monitor` is called with `type=MonitorType.PUSH` and a `name` of at most 150 characters, THE Library SHALL return a response containing `"msg": "Added Successfully."` and an integer `monitorID`, and the created monitor SHALL be retrievable via `get_monitor` using that `monitorID` with a non-empty `pushToken` field
6. IF `add_monitor` is called with valid parameters for any of the above monitor types and the Uptime Kuma v2.4.0 server returns a database constraint error, THEN THE Library SHALL raise an `UptimeKumaException` containing the error message from the server
7. WHEN any monitor is successfully created via criteria 1-5, THE Library SHALL complete the operation without raising `UptimeKumaException`, confirming the absence of NOT NULL constraint violations or other database errors that were present in pre-fix versions

### Requirement 7: Edit Monitor Preserves Conditions

**User Story:** As a developer editing monitors, I want the `edit_monitor` method to handle the `conditions` field correctly, so that editing a monitor does not cause constraint errors or data loss.

#### Acceptance Criteria

1. WHEN `edit_monitor` is called on an existing monitor whose fetched data already contains a `conditions` field and the caller does not supply a `conditions` parameter, THE Library SHALL preserve the existing `conditions` value from the fetched monitor data in the update payload sent to the server
2. WHEN `edit_monitor` is called on an existing monitor whose fetched data does not contain a `conditions` field and the caller does not supply a `conditions` parameter, THE Library SHALL include a `conditions` field set to an empty list in the update payload sent to the server
3. WHEN `edit_monitor` is called with an explicit `conditions` parameter containing a list, THE Library SHALL include the caller-provided `conditions` value in the update payload, overriding any value from the fetched monitor data
4. IF `edit_monitor` is called with a `conditions` parameter set to None, THEN THE Library SHALL convert it to an empty list in the update payload sent to the server
