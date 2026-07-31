## Changelog

### Release 2.3.0

Five confirmed library defects inherited from the original tracker, plus a documentation and provider-metadata sweep. No new public API surface: every change is corrective or additive, and v1.x version gating is unchanged. The reports and pull requests credited below were all filed against the original [lucasheld/uptime-kuma-api](https://github.com/lucasheld/uptime-kuma-api).

#### Bugfixes
- all seven `delete_*` methods now accept a string id. `delete_monitor("371")` raised `UptimeKumaException: monitor does not exist` for a monitor that demonstrably existed, because the existence guard compared the caller's string against the server's integer ids (`if id_ not in [i["id"] for i in ...]`). The id is now coerced to `int` before the membership test and the coerced value is sent to the server, at all seven affected sites: `delete_monitor`, `delete_notification`, `delete_proxy`, `delete_tag`, `delete_docker_host`, `delete_maintenance` and `delete_api_key`. An id that genuinely does not exist still raises the same `"... does not exist"` exception and sends nothing to the server; a non-numeric value passes through the coercion untouched. Reported in [lucasheld/uptime-kuma-api#91](https://github.com/lucasheld/uptime-kuma-api/issues/91) (credit: @ausebiblibre, PR #92).
- `get_status_page` now honours `ssl_verify`. The constructor passed `ssl_verify` only to `socketio.Client` and never stored it, so the `requests.get` that fetches the public status page JSON sent no `verify=` argument and always verified the certificate. `ssl_verify` is now stored on the instance and forwarded as `verify=self.ssl_verify`, so an `ssl_verify=False` caller can read a status page from a server with a self-signed certificate. The default remains `True` for both the socket.io connection and the HTTP call, and the returned status page structure is unchanged. Reported in [lucasheld/uptime-kuma-api#65](https://github.com/lucasheld/uptime-kuma-api/issues/65) (credit: @pr0kium, PR #81).
- `add_monitor_tag` and `delete_monitor_tag` no longer raise `TypeError: 'NoneType' object does not support item assignment`. Both write the freshly fetched monitor into the cached monitor list, which is `None` until a monitor list event has arrived, so a tag operation before that point failed *after* the tag had already been changed on the server. The cache is now initialised first, mirroring the pattern used in `add_status_page`. An already-populated cache is updated exactly as before. Reported in [lucasheld/uptime-kuma-api#68](https://github.com/lucasheld/uptime-kuma-api/issues/68).
- non-PEP440 server versions no longer crash every version gate. A server reporting a string such as `2.0.0-dev-nightly-20240101` made `packaging.version.parse` raise `InvalidVersion` at each of the roughly ten `parse_version(self.version)` gate sites, breaking operations that are otherwise supported. Version parsing now runs through a single private accessor that returns a max sentinel (`9999`) when the string is unparseable, treating an unrecognised build as the newest version so all `>=` gates evaluate `True`. Valid versions parse exactly as before, so v1.x versus v2.x gating is bit-for-bit identical. Reported in [lucasheld/uptime-kuma-api#74](https://github.com/lucasheld/uptime-kuma-api/issues/74).
- socket.io timeouts now raise the library's own `Timeout`. `_call` let `socketio.exceptions.TimeoutError` escape, so callers catching `Timeout` or `UptimeKumaException` did not catch a timed-out call, even though `get_status_page` already translated its `requests` timeout. `_call` now catches only `socketio.exceptions.TimeoutError` and re-raises `Timeout` (a subclass of `UptimeKumaException`); `SocketIOError` and every other transport error still propagate unchanged, and successful calls return the same `{"ok": ...}`-unwrapped result. Reported in [lucasheld/uptime-kuma-api#44](https://github.com/lucasheld/uptime-kuma-api/issues/44).

#### Notes
- **The `version` property still returns the raw server string.** The unparseable-version fix deliberately keeps normalisation out of the public `version` property and puts it in a new private `_parsed_version()` accessor that every gate site calls. Moving the fallback into `version` itself would have changed what a documented public property returns for a whole class of servers; as shipped, no public contract changed and only internal gating is affected. Callers who need the exact string the server reported still get it.

#### Documentation
- add the missing `MonitorType` import to the README context manager example and the `UptimeKumaApi` class docstring examples, which raised `NameError` as written (#78; credit: @Mirochill PR #95, @glerb #67)
- fix the `add_monitor` return key in the class docstring example (`monitorId` -> `monitorID`); the README copy of the same example was corrected in 2.2.1 (credit: @VadymKhvoinytskyi, PR #80)
- document in the `login` docstring and the README that the "API key" created in the Uptime Kuma web UI cannot authenticate this socket.io API — it only grants access to Uptime Kuma's Prometheus `/metrics` endpoint. Authenticate with a username and password, or with a login token via `login_by_token` (credit: @nneul PR #60; answers #73)
- update the documented unit test command in `CONTRIBUTING.md` and `AGENTS.md` to match the files CI actually runs

#### Metadata
Both corrections are behaviour-neutral: no method signature, accepted value or emitted payload changed.
- declare the SMTP notification option `smtpSecure` as `type="bool"` rather than `type="str"`, matching upstream `SMTP.vue`. This metadata drives the required-argument check, the generated notification docstrings and the downstream Ansible collection, so the declared type matters beyond documentation; the values accepted at runtime are unchanged (credit: @BergCyrill, PR #69)
- declare the `notificationIDList` default in `_build_monitor_data` as `[]` rather than `{}`, correcting the declared type. The runtime conversion to the server's `{id: True}` map is untouched, so the payload sent for both unset and populated notification lists is identical (credit: @obfusk, PR #57)

#### Tests
- add `tests/test_delete_id_coercion_v2.py`: 7 tests covering string id deletion at all seven `delete_*` sites, identical resolution for int and string ids, and absent ids of either type still raising and sending no delete
- extend the existing v2 unit files with 47 further regression tests: `test_status_page_v2.py` (`ssl_verify` forwarding and status page shape preservation), `test_monitor_params_v2.py` (monitor tag cache with a `None` and a populated cache, and version gate equivalence for valid, nightly and garbage version strings), `test_logger.py` (`_call` timeout translation plus non-timeout error and success pass-through), `test_notification_v2.py` (docstring examples, metadata types, and unchanged effective payloads). Every bug condition test was confirmed to fail against the pre-fix code.
- run `tests/test_status_page_incidents.py` in CI. It was added in 2.2.1 and documented as part of the unit suite, but was never listed in the GitHub Actions workflow, so its 10 tests had not actually been running.
- declare `python-dotenv` in `dev-requirements.txt`. Every `tests/live_test_*.py` script imports it, but it was declared nowhere, so a fresh clone could not run any of them. Development dependency only: the library itself does not import it and `install_requires` is unchanged.

### Release 2.2.1

Three status page bugs on Uptime Kuma 2.x, all found by testing against a live 2.4.0 instance and all verified fixed there.

#### Bugfixes
- `get_status_page` no longer drops incidents on Uptime Kuma 2.1.0+. The server renamed the singular, nullable `incident` object to a plural `incidents` array ([louislam/uptime-kuma#6469](https://github.com/louislam/uptime-kuma/pull/6469)). Release 2.0.0 stopped the resulting `KeyError` by switching to `.get()`, but the library still only read the singular key, so on 2.1.0+ it returned `incident: None` and silently discarded the incidents entirely. Both keys are now always returned regardless of server version: `incidents` holds the full list, `incident` holds the first entry for backward compatibility. Reported upstream in [lucasheld/uptime-kuma-api#85](https://github.com/lucasheld/uptime-kuma-api/issues/85).
- `save_status_page` no longer fails with `UptimeKumaException: Invalid analytics type` on any v2 status page that has no analytics configured. The v2 server requires `analyticsType` to be *present* in the payload and rejects the entire save when the key is absent; verified against 2.4.0 that `null` is accepted while an absent key, `""` and `"none"` are all rejected. The analytics fields are now sent unconditionally on v2, including when `None`. This also fixes `post_incident` and `unpin_incident`, which both call `save_status_page`.
- `add_status_page` now refreshes the cached status page list. Uptime Kuma sends no list event when a page is added, and `wait_for_event` only blocks while the cached value is `None`, so an already-populated cache was satisfied instantly and never learned about the new page. `get_status_pages` and `delete_status_page` could not see a page created in the same session, making `delete_status_page` raise `status page does not exist` for a page that demonstrably existed.

#### Tests
- add `tests/test_status_page_incidents.py`: 10 regression tests covering both incident shapes, null and empty arrays, multiple incidents, absence of both keys, and style parsing. Confirmed to fail against the pre-fix code.
- extend `tests/test_status_page_v2.py` with 3 tests asserting the v2 analytics keys are present when `None` and still absent on v1

#### Documentation
- API reference is now published on [Read the Docs](https://uptime-kuma-api2.readthedocs.io)
- add `MonitorBuilder` to the API reference (it was exported and documented in the README but missing from the generated docs)
- rewrite the project intro to describe an independent continuation of the original library, with credit and the retained MIT copyright, rather than a "fork"
- fix the `add_monitor` example return value (`monitorId` -> `monitorID`) and refresh the supported-version table

#### Packaging
- the GitHub repository was detached from the fork network and renamed from `uptime-kuma-api-v2` to `uptime-kuma-api2` to match the PyPI distribution; `project_urls` and the docs `github_repo` were updated accordingly (the old repository URL redirects)

### Release 2.2.0

No functional changes to the library. Packaging, documentation, and supported Python versions only.

#### BREAKING CHANGES
- Python 3.8+ required. Support for Python 3.7 is dropped; it has been end-of-life since June 2023 and was never covered by CI. Installs on 3.7 will resolve to 2.1.0 or earlier.

#### Documentation
- align README, Sphinx docs and install instructions with the published distribution name `uptime-kuma-api2` (the import package remains `uptime_kuma_api`)
- clarify that PyPI `uptime-kuma-api` (upstream) and `uptime-kuma-api-v2` (unrelated maintainer) are not this fork
- correct the documented test command: only the six v2 test files run without a live server, and warn that the inherited integration tests wipe all data on the target instance
- replace the Read the Docs link that pointed at the upstream project with local Sphinx build instructions

#### Packaging
- add `project_urls` (Source, Changelog, Issues) for the PyPI sidebar
- add Python 3.12 and 3.13 classifiers to match the versions CI tests
- add a valid `build` section to `.readthedocs.yaml` so Read the Docs builds can succeed
- bump Sphinx to 7.4.7; the previous 5.3.0 pin fails on Python 3.12+ because `imghdr` was removed
- ignore the `build/` directory

#### Bugfixes
- fix `SyntaxWarning: invalid escape sequence '\*'` raised on import under Python 3.12+ (`set_settings` docstring)
- fix Sphinx warnings: malformed literal block in the `UptimeKumaApi` docstring, missing `_static` path, and `install` missing from the toctree

### Release 2.1.0

#### Features
- add new monitor types: RabbitMQ, SNMP, SMTP, System Service
- add v2 monitor parameters: `jsonPathOperator`, `ipFamily`, `cacheBust`, `retryOnlyOnStatusCodeFailure`, `bearer_token`, `oauth_audience`, `domainExpiryNotification`, `saveResponse`, `saveErrorResponse`, `responseMaxLength`, `responsecheck`, `ping_count`, `ping_numeric`, `ping_per_request_timeout`, `mqttWebsocketPath`, `mqttCheckType`, `subtype`, `wsSubprotocol`, `wsIgnoreSecWebsocketAcceptHeader`, `remoteBrowsersToggle`, `remote_browser`, `screenshot_delay`, `gamedigToken`, `protocol`
- add v2 status page fields: `analyticsType`, `analyticsId`, `analyticsScriptUrl`, `showOnlyLastHeartbeat`, `rssTitle`
- add version-gated status page: remove `googleAnalyticsId` and `password` for v2, keep for v1
- add new notification providers: Nextcloud Talk, Brevo, Evolution API
- add `logger` parameter to `UptimeKumaApi` constructor (credit: @markus-seidl, PR #86)
- add `MonitorBuilder` fluent builder class for monitor configuration (credit: @markus-seidl, PR #86)
- add automatic v2-only parameter gating via `parse_version`

#### Tests
- add 86 unit tests covering all new features (no live server required):
  - `test_monitor_types_v2.py`: new monitor type payload assembly and required-field validation
  - `test_monitor_params_v2.py`: v2 parameter inclusion, version gating, input validation
  - `test_status_page_v2.py`: analytics replacement, password removal, new field routing
  - `test_notification_v2.py`: Nextcloud Talk, Brevo, Evolution API provider validation
  - `test_logger.py`: logger parameter type checking and socketio forwarding
  - `test_monitor_builder.py`: fluent builder chaining, build output, error handling

### Release 2.0.0

#### Features
- add support for Uptime Kuma 2.0.0 - 2.4.0
- add `conditions` parameter to `add_monitor` and `edit_monitor` for all monitor types
- incorporate upstream PR #87 (fix status page save for v2)
- incorporate upstream PR #88 (add conditions support for DNS monitors)

#### Bugfixes
- fix `SQLITE_CONSTRAINT: NOT NULL constraint failed: monitor.conditions` error on v2
- fix `save_status_page` TypeError caused by removed `autoRefreshInterval` field in v2

### Release 1.2.1

#### Bugfixes
- drop first info event without a version

### Release 1.2.0

#### Features
- add support for uptime kuma 1.23.0 and 1.23.1

#### Bugfixes
- remove `name` from maintenance monitors and status pages
- rstip url globally
- convert sendUrl from bool to int
- validate accepted status codes types

### Release 1.1.0

#### Features
- add support for uptime kuma 1.22.0 and 1.22.1

### Release 1.0.1

#### Bugfixes
- fix ValueError if monitor authMethod is None

### Release 1.0.0

#### Features
- add `ssl_verify` parameter
- add `wait_events` parameter
- implement context manager for UptimeKumaApi class
- drop Python 3.6 support
- implement `get_monitor_status` helper method
- implement timeouts for all methods (`timeout` parameter)
- add support for uptime kuma 1.21.3
- drop support for Uptime Kuma versions < 1.21.3
- check for required notification arguments
- raise exception when deleting an element that does not exist
- replace raw return values with enum values

#### Bugfixes
- adjust monitor `status` type to allow all used values
- fix memory leak

#### BREAKING CHANGES
- Python 3.7+ required
- maintenance parameter `timezone` renamed to `timezoneOption`
- Removed the `wait_timeout` parameter. Use the new `timeout` parameter instead. The `timeout` parameter specifies how many seconds the client should wait for the connection, an expected event or a server response.
- changed return values of methods `get_heartbeats`, `get_important_heartbeats`, `avg_ping`, `uptime`, `cert_info`
- Uptime Kuma versions < 1.21.3 are not supported in uptime-kuma-api 1.0.0+
- Removed the `get_heartbeat` method. This method was never intended to retrieve information. Use `get_heartbeats` or `get_important_heartbeats` instead.
- Types of return values changed to enum values:
  - monitor: `type` (str -> MonitorType), `status` (bool -> MonitorStatus), `authMethod` (str -> AuthMethod)
  - notification: `type` (str -> NotificationType)
  - docker host: `dockerType` (str -> DockerType)
  - status page: `style` (str -> IncidentStyle)
  - maintenance: `strategy` (str -> MaintenanceStrategy)
  - proxy: `protocol` (str -> ProxyProtocol)

### Release 0.13.0

#### Feature
- add support for uptime kuma 1.21.2
- implement custom socketio headers

#### Bugfix
- do not wait for events that have already arrived

### Release 0.12.0

#### Feature
- add support for uptime kuma 1.21.1

### Release 0.11.0

#### Feature
- add support for uptime kuma 1.21.0

### Release 0.10.0

#### Feature
- add support for uptime kuma 1.20.0

### Release 0.9.0

#### Feature
- add support for uptime kuma 1.19.5

### Release 0.8.0

#### Feature
- add support for uptime kuma 1.19.3

### Release 0.7.1

#### Bugfix
- remove unsupported type hints on old python versions

### Release 0.7.0

#### Feature
- add support for uptime kuma 1.19.2

#### Bugfix
- skip condition check for None values

### Release 0.6.0

#### Feature
- add parameter `wait_timeout` to adjust connection timeout

### Release 0.5.2

#### Bugfix
- add type to notification provider options

### Release 0.5.1

#### Bugfix
- remove required notification provider args check

### Release 0.5.0

#### Feature
- support for uptime kuma 1.18.3

### Release 0.4.0

#### Feature
- support for uptime kuma 1.18.1 / 1.18.2

#### Bugfix
- update event list data after changes

### Release 0.3.0

#### Feature
- support autoLogin for enabled disableAuth

#### Bugfix
- set_settings password is only required if disableAuth is enabled
- increase event wait time to receive the slow statusPageList event

### Release 0.2.2

#### Bugfix
- remove `tags` from monitor input
- convert monitor notificationIDList only once

### Release 0.2.1

#### Bugfix
- generate pushToken on push monitor save
- convert monitor notificationIDList return value

### Release 0.2.0

#### Feature
- support for uptime kuma 1.18.0

#### Bugfix
- convert values on monitor edit

### Release 0.1.1

#### Bugfix
- implement 2FA login
- allow to add monitors to status pages
- do not block certain methods

### Release 0.1.0

- initial release
