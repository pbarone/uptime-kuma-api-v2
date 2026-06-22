# Requirements Document

## Introduction

Implement the full backlog of Uptime Kuma v2 support items in the `uptime-kuma-api` Python library. Basic v2 compatibility (conditions field + autoRefreshInterval fix) has already shipped. This spec covers the remaining work: new monitor types, new monitor parameters, status page analytics changes, new notification providers, a logger parameter, a MonitorBuilder DTO, and version detection enhancements. Where applicable, implementations are cherry-picked from upstream PR #86 by @markus-seidl.

## Glossary

- **Library**: The `uptime-kuma-api` Python package that wraps the Uptime Kuma WebSocket/Socket.IO API
- **Monitor_Builder**: The `_build_monitor_data` method in `api.py` that assembles monitor payloads
- **Status_Page_Builder**: The `_build_status_page_data` method in `api.py` that assembles status page configuration payloads
- **MonitorType_Enum**: The `MonitorType` enum class in `monitor_type.py` enumerating all supported monitor type values
- **NotificationType_Enum**: The `NotificationType` enum class in `notification_providers.py` enumerating all notification provider identifiers
- **Notification_Provider_Params**: The notification provider parameter definitions in `notification_providers.py` that describe required/optional fields per provider
- **Version_Gate**: A conditional check using `parse_version(self.version) >= parse_version("2.0")` to enable v2-only behavior
- **UptimeKumaApi**: The main client class in `api.py` providing all public methods for interacting with Uptime Kuma
- **MonitorBuilder_DTO**: A fluent builder class for constructing monitor configuration dictionaries
- **PR_86**: Upstream pull request #86 by @markus-seidl containing v2 field additions, logger parameter, and MonitorBuilder DTO

## Requirements

### Requirement 1: New Monitor Types

**User Story:** As a developer managing Uptime Kuma v2 infrastructure, I want to create RabbitMQ, SNMP, SMTP, and System Service monitors through the API, so that I can monitor these service types programmatically.

#### Acceptance Criteria

1. THE MonitorType_Enum SHALL include values `RABBITMQ` (string value `"rabbitmq"`), `SNMP` (string value `"snmp"`), `SMTP` (string value `"smtp"`), and `SYSTEM_SERVICE` (string value `"system-service"`) matching the Uptime Kuma v2 server `name` property in each monitor-type class
2. WHEN `add_monitor` is called with `type=MonitorType.RABBITMQ`, THE Monitor_Builder SHALL accept parameters `rabbitmqNodes` (list of str, serialized as a JSON string in the payload), `rabbitmqUsername` (str, defaults to `""`), and `rabbitmqPassword` (str, defaults to `""`) and include them in the payload sent to the server
3. WHEN `add_monitor` is called with `type=MonitorType.SNMP`, THE Monitor_Builder SHALL accept parameters `snmpOid` (str), `snmpVersion` (str, one of `"1"`, `"2c"`, or `"3"`), and `snmp_v3_username` (str) and include them in the payload sent to the server along with the existing common parameters `hostname`, `port` (defaults to 161), `jsonPath`, `jsonPathOperator`, and `expectedValue`
4. WHEN `add_monitor` is called with `type=MonitorType.SMTP`, THE Monitor_Builder SHALL accept parameter `smtpSecurity` (str, one of `"secure"`, `"starttls"`, or `"nostarttls"`, defaults to `"starttls"`) and include it in the payload sent to the server along with the existing common parameters `hostname` and `port` (defaults to 25)
5. WHEN `add_monitor` is called with `type=MonitorType.SYSTEM_SERVICE`, THE Monitor_Builder SHALL accept parameter `system_service_name` (str) and include it in the payload sent to the server
6. THE `_check_arguments_monitor` function SHALL enforce required fields per new type: `MonitorType.RABBITMQ` requires `["rabbitmqNodes"]`, `MonitorType.SNMP` requires `["hostname", "snmpOid"]`, `MonitorType.SMTP` requires `["hostname"]`, and `MonitorType.SYSTEM_SERVICE` requires `["system_service_name"]`
7. WHEN any new monitor type is created with all required fields populated, THE Library SHALL return a response containing `"msg": "Added Successfully."` and an integer `monitorID` with a value greater than 0
8. IF `add_monitor` is called with a new monitor type and a required field is missing, THEN THE Library SHALL raise a `TypeError` or equivalent validation error indicating the missing field name before sending any payload to the server

### Requirement 2: New Monitor Parameters for JSON_QUERY and Network Monitors

**User Story:** As a developer using JSON query monitors, I want to specify comparison operators beyond equality, so that I can validate numeric thresholds and pattern matches in API responses.

#### Acceptance Criteria

1. THE Monitor_Builder SHALL accept a `jsonPathOperator` parameter (str, default None) in the `_build_monitor_data` method signature, positioned in the JSON_QUERY parameter section alongside `jsonPath` and `expectedValue`
2. WHEN `add_monitor` or `edit_monitor` is called with a non-None `jsonPathOperator` value for a monitor of type `JSON_QUERY`, THE Monitor_Builder SHALL include the `jsonPathOperator` field in the payload sent to the server with its value unchanged
3. IF `add_monitor` or `edit_monitor` is called with a non-None `jsonPathOperator` value for a monitor whose type is not `JSON_QUERY`, THEN THE Monitor_Builder SHALL omit `jsonPathOperator` from the payload sent to the server
4. THE Monitor_Builder SHALL accept an `ipFamily` parameter (str, default None) in the `_build_monitor_data` method signature, applicable to network-based monitor types: HTTP, KEYWORD, JSON_QUERY, PING, PORT, DNS, STEAM, MQTT, RADIUS, TAILSCALE_PING, GRPC_KEYWORD, SNMP, SMTP, and RABBITMQ
5. WHEN `add_monitor` or `edit_monitor` is called with a non-None `ipFamily` value for a monitor whose type is one of the network-based types listed in criterion 4, THE Monitor_Builder SHALL include the `ipFamily` field in the payload sent to the server with its value unchanged
6. IF `add_monitor` or `edit_monitor` is called with a non-None `ipFamily` value for a monitor whose type is not in the network-based types listed in criterion 4, THEN THE Monitor_Builder SHALL omit `ipFamily` from the payload sent to the server

### Requirement 3: New HTTP Monitor Parameters

**User Story:** As a developer configuring HTTP monitors, I want access to cache-busting, Bearer auth, response saving, and domain expiry notification options, so that I can fine-tune HTTP monitoring behavior through the API.

#### Acceptance Criteria

1. THE Monitor_Builder SHALL accept the following additional parameters for HTTP-based monitor types (HTTP, KEYWORD, JSON_QUERY, REAL_BROWSER where applicable): `cacheBust` (bool, default None), `retryOnlyOnStatusCodeFailure` (bool, default None), `bearer_token` (str, default None), `oauth_audience` (str, default None), `domainExpiryNotification` (bool, default None), `saveResponse` (bool, default None), `saveErrorResponse` (bool, default None), `responseMaxLength` (int, default None, valid range 1 to 10,000,000 characters), and `responsecheck` (str, default None, maximum 2048 characters)
2. WHEN any of the HTTP parameters listed in criterion 1 are provided with a non-None value, THE Monitor_Builder SHALL include those fields in the payload sent to the server, leaving their values unchanged
3. WHEN a monitor is created or edited without specifying the parameters listed in criterion 1, THE Monitor_Builder SHALL omit those fields from the payload (i.e., the keys SHALL NOT be present in the dict passed to `_call`), relying on server-side defaults
4. IF `responseMaxLength` is provided with a value less than 1 or greater than 10,000,000, THEN THE Monitor_Builder SHALL raise a ValueError indicating the value is out of range
5. WHEN `bearer_token` is provided with a non-None value, THE Monitor_Builder SHALL include the `bearer_token` field in the payload independently of the `authMethod` parameter (i.e., it does not require `authMethod` to be set to a specific value)

### Requirement 4: New PING Monitor Parameters

**User Story:** As a developer configuring PING monitors, I want to control ping count, numeric output mode, and per-request timeout, so that I can customize PING monitoring behavior.

#### Acceptance Criteria

1. THE Monitor_Builder SHALL accept `ping_count` (int, default None), `ping_numeric` (bool, default None), and `ping_per_request_timeout` (int, default None) parameters for monitors of type `PING`
2. WHEN any PING-specific parameter is provided with a non-None value and the monitor type is `PING`, THE Monitor_Builder SHALL include those fields in the payload sent to the server
3. WHEN a PING monitor is created without specifying PING-specific parameters, THE Monitor_Builder SHALL omit those fields from the payload

### Requirement 5: New MQTT Monitor Parameters

**User Story:** As a developer configuring MQTT monitors, I want to specify a websocket transport path and check mode, so that I can monitor MQTT brokers with advanced configurations.

#### Acceptance Criteria

1. THE Monitor_Builder SHALL accept `mqttWebsocketPath` (str, default None, maximum 255 characters) and `mqttCheckType` (str, default None, allowed values: `"keyword"` or `"json-query"`) parameters for monitors of type `MQTT`
2. WHEN either MQTT parameter is provided with a non-None value and the monitor type is `MQTT`, THE Monitor_Builder SHALL include those fields in the payload sent to the server
3. IF `mqttCheckType` is provided with a value other than None, `"keyword"`, or `"json-query"`, THEN THE Monitor_Builder SHALL reject the input with an error indicating the invalid check type value
4. IF `mqttWebsocketPath` is provided with a string exceeding 255 characters, THEN THE Monitor_Builder SHALL reject the input with an error indicating the path exceeds the maximum length

### Requirement 6: Low-Priority Monitor Parameters

**User Story:** As a developer managing SSH, Websocket, Real Browser, and Gamedig monitors, I want access to their v2-specific parameters, so that I can configure advanced options.

#### Acceptance Criteria

1. THE Monitor_Builder SHALL accept the following low-priority parameters with default value None: `subtype` (str), `wsSubprotocol` (str), `wsIgnoreSecWebsocketAcceptHeader` (bool), `remoteBrowsersToggle` (bool), `remote_browser` (str), `screenshot_delay` (int, range 0 to 60000 milliseconds), `gamedigToken` (str), and `protocol` (str)
2. WHEN any low-priority parameter is provided with a non-None value, THE Monitor_Builder SHALL include that parameter and its value in the payload sent to the server
3. WHEN a monitor is created or edited without specifying low-priority parameters, THE Monitor_Builder SHALL omit those fields from the payload, ensuring they are not sent as None to the server
4. WHEN editing a monitor that already has low-priority parameter values set on the server, THE Monitor_Builder SHALL preserve those existing values in the payload if the user does not explicitly override them

### Requirement 7: Status Page Analytics Replacement

**User Story:** As a developer managing status pages on Uptime Kuma v2, I want to configure analytics using the new v2 analytics fields, so that I can set up tracking without relying on the removed Google Analytics ID field.

#### Acceptance Criteria

1. WHEN connected to Uptime Kuma v2 (version >= 2.0), THE Status_Page_Builder SHALL accept parameters `analyticsType` (str, default None), `analyticsId` (str, default None), and `analyticsScriptUrl` (str, default None) in the `_build_status_page_data` method signature
2. WHEN connected to Uptime Kuma v2 and the caller provides one or more analytics parameters (`analyticsType`, `analyticsId`, `analyticsScriptUrl`), THE Status_Page_Builder SHALL include all three fields in the status page config payload, using None for any parameter not explicitly provided by the caller
3. WHEN connected to Uptime Kuma v2, THE Status_Page_Builder SHALL omit the `googleAnalyticsId` field from the config payload
4. WHEN connected to Uptime Kuma v1 (version < 2.0), THE Status_Page_Builder SHALL accept and include `googleAnalyticsId` in the payload and SHALL silently discard any v2 analytics parameters (`analyticsType`, `analyticsId`, `analyticsScriptUrl`) without raising an error or warning
5. THE Library SHALL use the existing `parse_version(self.version) >= parse_version("2.0")` pattern to determine which analytics fields to include in the status page config payload
6. WHEN connected to Uptime Kuma v2 and the server returns `googleAnalyticsId` in the fetched status page data, THE Status_Page_Builder SHALL remove `googleAnalyticsId` from the fetched data before passing it to `_build_status_page_data`, preventing unexpected keyword argument errors

### Requirement 8: Status Page Password Removal for v2

**User Story:** As a developer managing status pages, I want the library to handle the removal of password protection in v2, so that save operations do not send unsupported fields.

#### Acceptance Criteria

1. WHEN connected to Uptime Kuma v2 (version >= 2.0), THE Status_Page_Builder SHALL omit the `password` field from the status page config payload sent to the server
2. WHEN connected to Uptime Kuma v1 (version < 2.0) and a `password` value is provided, THE Status_Page_Builder SHALL include the `password` field in the status page config payload
3. WHEN connected to Uptime Kuma v1 (version < 2.0) and no `password` value is provided, THE Status_Page_Builder SHALL omit the `password` field from the status page config payload
4. THE Library SHALL determine whether to include or omit the `password` field by comparing the connected server version against the threshold version 2.0 using the existing `parse_version` mechanism
5. IF a caller provides a `password` parameter while connected to Uptime Kuma v2 (version >= 2.0), THEN THE Library SHALL silently ignore the `password` value without raising an error

### Requirement 9: New Status Page Fields

**User Story:** As a developer configuring status pages, I want to set the "show only last heartbeat" option and customize the RSS feed title, so that I can control v2 status page display behavior.

#### Acceptance Criteria

1. THE Status_Page_Builder SHALL accept `showOnlyLastHeartbeat` (bool, default None) and `rssTitle` (str, default None) as optional parameters in `_build_status_page_data`
2. IF `showOnlyLastHeartbeat` is provided with a non-None value and the server version is >= 2.0, THEN THE Status_Page_Builder SHALL include `showOnlyLastHeartbeat` in the status page config dict sent to the server
3. IF `rssTitle` is provided with a non-None value and the server version is >= 2.0, THEN THE Status_Page_Builder SHALL include `rssTitle` in the status page config dict sent to the server
4. IF the server version is < 2.0, THEN THE Status_Page_Builder SHALL omit `showOnlyLastHeartbeat` and `rssTitle` from the status page config dict regardless of the values provided
5. WHEN `save_status_page` retrieves existing status page data that contains `showOnlyLastHeartbeat` or `rssTitle` fields, THE Status_Page_Builder SHALL pass these fields through to `_build_status_page_data` without raising an exception

### Requirement 10: New Notification Providers

**User Story:** As a developer configuring notifications, I want to use Nextcloud Talk, Brevo, and Evolution API as notification providers, so that I can send alerts through these services.

#### Acceptance Criteria

1. THE NotificationType_Enum SHALL include values for Nextcloud Talk with string identifier `"nextcloudtalk"`, Brevo with string identifier `"Brevo"`, and Evolution API with string identifier `"evolution"`
2. THE Notification_Provider_Params SHALL define the following fields for the Nextcloud Talk notification provider: required fields `host` (str), `conversationToken` (str), `botSecret` (str); optional fields `sendSilentUp` (bool), `sendSilentDown` (bool)
3. THE Notification_Provider_Params SHALL define the following fields for the Brevo notification provider: required fields `brevoApiKey` (str), `brevoFromEmail` (str), `brevoToEmail` (str); optional fields `brevoFromName` (str), `brevoCcEmail` (str), `brevoBccEmail` (str), `brevoSubject` (str)
4. THE Notification_Provider_Params SHALL define the following fields for the Evolution API notification provider: required fields `evolutionInstanceName` (str), `evolutionAuthToken` (str), `evolutionRecipient` (str); optional fields `evolutionApiUrl` (str), `evolutionUseCustomMessage` (bool), `evolutionCustomMessage` (str)
5. WHEN `add_notification` is called with `type` set to any of the three new notification types and all required provider-specific parameters supplied with non-empty string values, THE Library SHALL return a response containing an `id` (int) and `msg` (str) indicating the notification was created
6. IF `add_notification` is called with any of the three new notification types but one or more required provider-specific parameters are missing, THEN THE Library SHALL raise an exception indicating the missing required arguments before sending data to the server

### Requirement 11: Logger Parameter

**User Story:** As a developer debugging Socket.IO communication issues, I want to pass a custom logger to the UptimeKumaApi client, so that I can capture and inspect protocol-level debug output.

#### Acceptance Criteria

1. THE UptimeKumaApi constructor SHALL accept an optional `logger` parameter (default None) that accepts a Python `logging.Logger` instance or a boolean value
2. WHEN a non-None `logger` value is provided, THE UptimeKumaApi SHALL pass the `logger` value to the `socketio.Client` constructor as the `logger` parameter
3. WHEN `logger` is not provided or is None, THE UptimeKumaApi SHALL construct the `socketio.Client` without a logger argument, preserving existing default behavior
4. IF the `logger` parameter value is not an instance of `logging.Logger`, not a boolean, and not None, THEN THE UptimeKumaApi SHALL raise a TypeError indicating the accepted types
5. THE Library SHALL credit @markus-seidl (PR #86) in the commit message implementing this feature

### Requirement 12: MonitorBuilder DTO

**User Story:** As a developer creating complex monitor configurations, I want a fluent builder pattern for constructing monitor payloads, so that I can compose configurations step-by-step with IDE autocompletion support.

#### Acceptance Criteria

1. THE Library SHALL provide a `MonitorBuilder` class that exposes a fluent interface for constructing monitor configuration dictionaries
2. THE MonitorBuilder_DTO SHALL provide setter methods for all parameters accepted by the Monitor_Builder, where each setter method returns the MonitorBuilder_DTO instance to enable method chaining
3. THE MonitorBuilder_DTO SHALL provide a `build()` method that returns a dictionary containing only explicitly-set fields, suitable for passing to `add_monitor` or `edit_monitor` as keyword arguments
4. WHEN `build()` is called on a MonitorBuilder_DTO that has not had a `type` or `name` set, THE MonitorBuilder_DTO SHALL raise a ValueError indicating which required fields are missing
5. WHEN a setter method is called multiple times on the same MonitorBuilder_DTO instance, THE MonitorBuilder_DTO SHALL use the value from the most recent call, overwriting any previously set value
6. THE `build()` method SHALL include a `type` field with the MonitorType enum value (not the string representation) ensuring compatibility with `add_monitor` and `edit_monitor` kwargs
7. THE Library SHALL credit @markus-seidl (PR #86) in the commit message implementing this feature

### Requirement 13: Version Detection Enhancement

**User Story:** As a library maintainer, I want v2-only parameters to be automatically gated behind a version check, so that sending unsupported fields to v1 instances does not cause unexpected behavior.

#### Acceptance Criteria

1. WHEN the UptimeKumaApi receives the `info` event containing a `version` field after login, THE Library SHALL cache the server version string and make it available via the `version` property for use in subsequent payload-building operations
2. WHEN `_build_monitor_data` includes v2-only parameters (parameters listed in the "New Monitor Parameters" section of the backlog that apply only to Uptime Kuma >= 2.0), THE Library SHALL include those parameters in the payload only when `parse_version(self.version) >= parse_version("2.0")`
3. IF connected to a v1 instance (detected version < 2.0) and v2-only monitor parameters are provided by the caller, THEN THE Library SHALL omit those parameters from the payload without raising an error or logging a warning
4. WHEN connected to a v2 instance (detected version >= 2.0), THE Library SHALL include all provided v2-only parameters in the payload without requiring the caller to perform version checks
5. IF the `version` property is accessed before the `info` event has been received or the `info` event does not contain a `version` field, THEN THE Library SHALL raise an `UptimeKumaException` indicating that the server version is unavailable

### Requirement 14: PR #86 Attribution

**User Story:** As a library maintainer, I want proper attribution for cherry-picked work, so that open-source contributions are credited correctly.

#### Acceptance Criteria

1. WHEN implementing monitor parameters that originate from PR #86, THE Library commit messages SHALL include a "Co-authored-by: @markus-seidl" trailer and a reference to PR #86 in the commit body
2. WHEN implementing the logger parameter for UptimeKumaApi.__init__, THE Library commit messages SHALL include a "Co-authored-by: @markus-seidl" trailer and a reference to PR #86 in the commit body
3. WHEN implementing the MonitorBuilder DTO class, THE Library commit messages SHALL include a "Co-authored-by: @markus-seidl" trailer and a reference to PR #86 in the commit body
4. THE Library SHALL NOT adopt the `get_monitors` event-handling refactor from PR #86
5. THE Library SHALL NOT adopt the `conditions if conditions else list()` pattern from PR #86 that replaces an intentional empty list with a new list allocation
