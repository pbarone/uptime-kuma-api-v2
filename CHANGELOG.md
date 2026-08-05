## Changelog
### Unreleased
#### Packaging
- add a `MANIFEST.in` so the sdist is self-consistent. The sdist shipped 29 `tests/test_*.py` files but not `tests/uptime_kuma_test_case.py`, the base class every one of the inherited integration tests extends, so as published those 29 files could not even be imported from the sdist, let alone run. `CHANGELOG.md` was also absent despite `project_urls` advertising a Changelog link. Both are now included. The cause was that with no `MANIFEST.in` at all the file list was setuptools' default, whose only `tests/` pattern is `tests/test*.py` (`_add_defaults_optional` in `setuptools/_distutils/command/sdist.py`, read from the installed 83.0.0 rather than inferred). **That same pattern was also the only thing keeping `tests/.env`, `tests/.backups/**` and `tests/live_test_*.py` out of the published artifact** — none of those names begins with `test`, so their absence and the base class's absence had one shared cause, and it was a coincidence of spelling rather than a policy. The two new lines are therefore narrow `include` directives, and `MANIFEST.in` carries an explicit warning against broadening them to `recursive-include tests` or `graft tests`, which would sweep real credentials and config snapshots into an artifact that cannot be withdrawn once published. Nothing was removed: the change is exactly three added members (`CHANGELOG.md`, `tests/uptime_kuma_test_case.py`, and `MANIFEST.in` itself, which setuptools always ships), verified by diffing the complete member list of a before-and-after sdist rather than by inspecting the new one. `MANIFEST.in` also carries `global-exclude` lines for `.env`, `.live_test_ids.json`, `live_test_*.py` and `*.pyc` plus `prune tests/.backups`, and **these are load-bearing rather than decorative**. `manifest_maker.run` calls `add_defaults()` — which reads any existing `*.egg-info/SOURCES.txt` back into the file list — *before* `read_template()` processes `MANIFEST.in`, so the exclusions are applied on top of whatever a stale manifest dragged in and strip it. Measured against a deliberately poisoned `SOURCES.txt`: with only the two `include` lines the build shipped 111 members including `tests/.env` and all three credential-bearing `tests/.backups/config_snapshot_*.json`; with the exclusions present the same poisoned tree produced 61 members and **zero** credentials. `global-exclude` rather than `exclude` because there is a credential-bearing `.env` at the repository root as well as under `tests/`. The cost is five `no previously-included files matching` warnings on every clean build, which is the correct trade and is now documented in `MANIFEST.in` as the healthy state: the warnings mean the guard found nothing to remove, and their *absence* would mean a pattern actually fired. One limit is worth stating precisely, because it is what the allowlist below exists for: `MANIFEST.in` directives apply in file order, so a broad include appended *below* the exclusions defeats them. Pre-existing rather than a regression; the 2.2.1 and 2.3.0 sdists have the same shape. No runtime change: no file under `uptime_kuma_api/` was touched, the wheel is unaffected, and no public method, parameter, class or export was added. Reported in [pbarone/uptime-kuma-api2#13](https://github.com/pbarone/uptime-kuma-api2/issues/13).
- gate releases on `scripts/check_sdist.py`, which turns "no credentials in the sdist" from a habit into a mechanism. Earlier releases verified it by hand — the 2.3.1 release-prep commit records checking that the sdist held "no live_test scripts, no .env and no .backups" — but a manual check cannot protect a future release. The script asserts the required members are present and then **allowlists** `tests/` to `test_*.py` plus the base class, failing on anything else; an allowlist rather than a denylist of known-bad names, because the risk being guarded against is a file nobody thought to enumerate. It runs in `publish.yml` after `twine check` and before `twine upload`, against `dist/*.tar.gz` — the exact tarball about to be published, not a rebuild of it that is merely assumed to match — and again in a new `sdist` workflow at PR time. Both placements earn their keep: the publish-time run is what stops a leak reaching PyPI, while the PR-time run is what stops a *tag* being burned, since `protect-release-tags` blocks `deletion` on `v*` and a release-time failure lands after the tag is already immutable. The check was proven able to fail rather than merely observed passing: injecting `graft tests` into `MANIFEST.in` produced 51 violations naming `tests/.env`, all three `tests/.backups/config_snapshot_*.json` and all six `tests/live_test_*.py`. **A second, quieter leak route was found and reproduced while writing it.** `manifest_maker.add_defaults` reads an existing `*.egg-info/SOURCES.txt` back into the file list when no revision-control plugin is installed, so a tree that built once with a broad pattern keeps shipping those files after the pattern is reverted: with `MANIFEST.in` holding nothing but the two `include` lines, `python -m build` still produced a 111-member sdist carrying `tests/.env` and the three credential-bearing config snapshots, purely from the stale `SOURCES.txt` left by the preceding experiment. CI is immune because it builds a fresh checkout; a local `python -m build` is not, which is why the script deletes the egg-info before building in build mode, and why a hand-run build is no longer what a release depends on. With the `MANIFEST.in` exclusions in place that route can no longer leak a credential — the residue it still produces is a tracked, non-secret `tests/.env.example`, which this check rejects anyway, on the principle that the sdist's contents should be exact and not merely safe. The new workflow is deliberately its own file rather than a job in `test.yml`, whose six `full (3.x)` checks are required by name in `protect-main` and which is slated for conversion to `workflow_call` under [#11](https://github.com/pbarone/uptime-kuma-api2/issues/11); it is advisory until `contents` is added to the required-check list. `scripts/` is tooling and stays out of both artifacts.
- remove the inherited `setup.py publish` shortcut, which was the one path that could upload to PyPI while bypassing every gate. It ran `rm dist/*`, `python setup.py sdist` and `twine upload dist/*` directly, so it skipped the tag/`__version__` match check, `twine check` and the new sdist contents check alike — and because it built locally rather than from a fresh checkout, it was also the only route by which the stale-`SOURCES.txt` behaviour described above could actually reach PyPI, publishing `tests/.env` and the credential-bearing `tests/.backups/**` snapshots. It was additionally broken on this project's own development platform: `rm` does not exist on Windows, so the first command failed and the following two ran anyway against whatever `dist/` already held, which for a tree carrying older artifacts means attempting to re-upload previously published files. Releases go through the tag-triggered publish workflow, which is gated and version-checked, so nothing is lost; a comment at the former location records what was removed and why. Not public API: it was a maintainer command-line shortcut, never an exported name, and `import sys` went with it as its only remaining user. Verified after removal that `python -m build` still produces both artifacts, `twine check` passes both, and the wheel metadata is byte-identical in name, version, `Requires-Python` and all three `Requires-Dist` entries.

### Release 2.3.1

A patch release: one v1.x correctness fix, one packaging correction, and three documentation gaps closed. No public method, parameter, class or export was added, and behaviour on Uptime Kuma 2.x is unchanged throughout. It also carries this project's **first outside contribution** — see the `run_tests.sh` entry under Tests.

#### Bugfixes
- the four v2-only monitor types are now rejected on pre-2.0 servers instead of being sent. `RABBITMQ`, `SNMP`, `SMTP` and `SYSTEM_SERVICE` exist only on Uptime Kuma 2.x, but neither `_build_monitor_data` nor `edit_monitor` compared the requested `type` against the server version. `add_monitor` / `edit_monitor` with one of these types against a server older than 2.0 now raises `UptimeKumaException: monitor type '<type>' requires Uptime Kuma 2.0 or newer, but the server reports version <observed>`, before any payload is built and before any server call. **The failure this replaces was worse than "the server rejects it", in both directions, and that is why it is a fix rather than a documented limitation.** What failed before was not the type: a 1.x server does not validate `type` when a monitor is added — `Monitor.validate()` in `server/model/monitor.js` checks interval bounds and nothing else, and the type is first consulted at *beat* time. Verified against a disposable 1.23.17 container: sending one of these types today fails with ``UptimeKumaException: insert into `monitor` (...) - SQLITE_ERROR: table monitor has no column named rabbitmq_nodes`` (or `snmp_oid` / `smtp_security` / `system_service_name`) — an opaque error naming a snake_case database column the caller never typed, and one that only fires because the library also sends that column. With those companion columns absent from the payload, the same server **accepts** the type, answers `{'msg': 'Added Successfully.', 'monitorID': n}`, and creates a monitor that sits `PENDING` indefinitely reporting `Unknown Monitor Type` — identically to a deliberately invented type string, which is the proof that the type value itself is never checked. So the old loud failure was a byproduct of the companion-field payload rather than a guarantee, and gating those fields (a tracked follow-up, [#14](https://github.com/pbarone/uptime-kuma-api2/issues/14)) would have converted it into a silent one. Provenance for the list is upstream source and tags, not inference: `rabbitmq` (`c01494ec`, first tag 2.0.0), `snmp` (`d92003e1`, 2.0.0), `smtp` (`c67f6efe`, 2.0.0), `system-service` (`0f951ef1`, 2.1.0); `git tag --contains` returns **no** 1.x tag for any of the four, and none of the three type strings appears anywhere in `server/` or `src/` at tag `1.23.17` (the `smtp` string does, but only as the "Email (SMTP)" *notification provider*, which is unrelated and unaffected). Behaviour on 2.x is unchanged: all four types build byte-identical payloads with every companion field intact, and a server reporting an unparseable version is still treated as newest, so all four remain permitted there. Types present on both majors are untouched, and `MonitorType` itself is unchanged — no member removed, renamed or re-valued. The `edit_monitor` guard reads the caller's own `kwargs`, not the merged monitor, so editing an unrelated field on a monitor that already carries one of these types cannot raise spuriously. No public method, parameter, class or export was added: the guard is a private helper and the type set a private module constant, and a new exception message is not API surface. Reported in [pbarone/uptime-kuma-api2#12](https://github.com/pbarone/uptime-kuma-api2/issues/12).

#### Notes
- **The gate is 2.0 for all four types, which leaves `SYSTEM_SERVICE` under-gated on 2.0.x, and a caller cannot derive that from the message.** `system-service` first appears in **2.1.0**, not 2.0.0, so requesting it against a 2.0.x server passes this gate and still creates a monitor that sits `PENDING` indefinitely reporting `Unknown Monitor Type` — the same outcome the gate prevents on 1.x. The other three (`rabbitmq`, `snmp`, `smtp`) are 2.0.0 types and are fully covered. A per-type version floor was considered and deliberately declined: 2.0 is the boundary the entire codebase gates on, it fully covers the v1.x defect this fix exists to close, and a `SYSTEM_SERVICE`-only floor would be the library's single per-type floor — that belongs with the one-rule work in [#14](https://github.com/pbarone/uptime-kuma-api2/issues/14) rather than here, since it is a new narrowing for v2 users rather than a v1 fix. Stated here rather than left in the spec because 2.0.0 is a supported target (`run_tests.sh` exercises it) and the raised message names `2.0`, so nothing a 2.0.x caller sees would reveal the gap.
- **The signalling for this rejection is provisional.** It raises a plain `UptimeKumaException`, which is deliberately the coarse choice. [#14](https://github.com/pbarone/uptime-kuma-api2/issues/14) ("Define one rule for v2-only fields on older servers") may narrow it to a dedicated subclass; because `Timeout` already demonstrates that a subclass of `UptimeKumaException` keeps every existing `except UptimeKumaException` catcher working, that later narrowing is additive rather than breaking. What is *not* provisional is the decision to reject: #14 may change the exception class or add a field-level signal, but it cannot make an unsupported monitor type work, which is why this fix ships ahead of it rather than waiting for it.
- **This does not contradict the `conditions` policy ratified in 2.3.0; it satisfies the condition that policy was contingent on.** That policy declined to raise for seven adjacent v2-only *fields* on the explicit grounds that whether each actually fails on v1 was **unverified**, so raising "would convert a possibly-working path into a guaranteed hard error". For these four types there is no working path to convert: both reachable outcomes on a 1.x server are failures (the opaque `SQLITE_ERROR`, or the silently-`PENDING` monitor), because a 1.x server contains no implementation of the type. A monitor type is also not a parameter whose loss can be degraded the way a dropped `bearer_token` or `ipFamily` is — it is the thing being requested, so "omit it silently" is not an available outcome. The seven fields keep their silent omission, unchanged.
- **The 2.3.0 note on `snmp_v3_username` was right in its conclusion and wrong in its mechanism.** It reasoned that gating that field was "close to a no-op anyway: the `SNMP` monitor type is itself v2-only, so a v1 server rejects the monitor type before the field matters". A v1 server does not reject the type. It rejects `snmp_oid`, and only because `snmp_oid` is sent. Gating the field remains correct and remains a no-op in practice; the reason recorded for it was not.

#### Documentation
- document the three exported symbols that were missing from the API reference: `Event`, `notification_provider_options` and `notification_provider_conditions`. `uptime_kuma_api/__init__.py` exports 15 names while `docs/api.rst` carried 12 autodoc directives, and those three were the entire difference, so they never reached the published reference on Read the Docs despite being public. Nothing flagged it, and nothing could have: Sphinx autodoc has no discovery mechanism, documents only what the `.rst` names, and emits **no warning** for an export it never sees — so a clean docs build looks identical whether the symbols are covered or not, and the only way to detect the gap is to diff the export list against the directive list by hand. `Event` also gained a class docstring, because it was the one enum in the package with neither a class docstring nor per-member ones, so `:members:` alone rendered an empty entry; it is documented with `:undoc-members:` so all 20 event names and their wire values appear. The two provider tables are documented with `py:data::` rather than `autodata::` for two reasons found while building: `autodata` inherits the built-in `dict` docstring for both symbols and tries to parse it as reStructuredText, which emitted 8 warnings and errors (the `**kwargs` in that docstring reads as an unterminated bold marker), and it would also have dumped `notification_provider_options`' full 13,185-character `repr` into the page, which is worse for a reader than the omission it replaced. Reported in [pbarone/uptime-kuma-api2#8](https://github.com/pbarone/uptime-kuma-api2/issues/8).
- name the two `Event` members added in 2.3.0. That release's notes described the monitor-list cache fix in terms of the wire event names (`updateMonitorIntoList`, `deleteMonitorFromList`) and never gave the enum members, so `Event.UPDATE_MONITOR_INTO_LIST` and `Event.DELETE_MONITOR_FROM_LIST` — both usable by callers today, since `Event` is exported from `__init__.py` — could not be identified from the changelog alone. Recorded here rather than retrofitted into the 2.3.0 section, which stays as it was written. No code change: both members have existed since 2.3.0, and this only closes the gap in the record of them. Reported in [pbarone/uptime-kuma-api2#7](https://github.com/pbarone/uptime-kuma-api2/issues/7).
- record the server versions this project supports and tests against, which no changelog entry had stated. The supported range is **Uptime Kuma 1.21.3 through 2.5.0** from a single install, with server-version-specific behaviour gated at runtime rather than split across separate library lines. `run_tests.sh` exercises the gate boundaries across that range — 2.5.0, 2.1.0, 2.0.0, 1.23.2, 1.23.0, 1.22.1, 1.22.0 and 1.21.3 — and this tree was additionally live-verified end to end against 1.23.2 and 2.5.0. `README.md` carried the range but `CHANGELOG.md` contained no occurrence of `2.5.0` at all, so when support for it arrived could not be reconstructed from the changelog. Servers older than 1.21.3 remain unsupported; that floor was set in uptime-kuma-api 1.0.0. Reported in [pbarone/uptime-kuma-api2#7](https://github.com/pbarone/uptime-kuma-api2/issues/7).

#### Packaging
- declare `requests` as a runtime dependency. `api.py` imports `requests` at module scope for the `get_status_page` HTTP fetch, but it was declared in neither `install_requires` nor `requirements.txt`; it resolved only as a side effect of `python-socketio`'s `[client]` extra, which declares `requests>=2.21.0`. Two consequences, both latent rather than active: a load-bearing import that no manifest accounted for, so a future restructuring of that extra would break `import uptime_kuma_api` for every user with nothing in this project's metadata to explain why; and no dependency-scanning visibility, so a `requests` or `urllib3` advisory raised no alert against this repository despite shipped code importing it. The declared floor is `>=2.21.0`, matching what the extra already guaranteed, so no install that resolves today stops resolving and no version is newly excluded. Nothing about the runtime changed: no import, call or signature was touched, and the same `requests` version is installed as before. Reported in [pbarone/uptime-kuma-api2#10](https://github.com/pbarone/uptime-kuma-api2/issues/10).

#### Tests
- extend `tests/test_monitor_params_v2.py` with 13 tests in two new classes for the v2-only monitor type gate: each of the four types rejected on v1 through `_build_monitor_data` (message asserted to name the type's string value, `2.0` and the observed version), the guard asserted to fire ahead of the preamble's own `ValueError` checks, a raw `"snmp"` string gated identically to the enum member, `edit_monitor` raising before `get_monitor` or `_call` is reached, a `MonitorBuilder` config rejected at the `add_monitor` boundary — and, on the preservation side, all four accepted on v2 with their companion fields intact, types present on both majors explicitly asserted *not* to raise on v1, the recorded v1 HTTP payload baseline unchanged key for key, the `conditions` guard still winning when a call trips both, an unparseable version still permitting all four, and `MonitorType` plus the package's public exports asserted untouched. The bug-condition tests were confirmed to fail against the unfixed code — 14 failures, all `UptimeKumaException not raised` — while all 11 preservation tests passed both before and after, which is what they are for. No new test file: the CI unit-file list is duplicated across `CONTRIBUTING.md`, `AGENTS.md`, `.github/workflows/test.yml`, `run_tests.sh` and the steering files, so a tenth file would be a seven-place edit. No pre-existing class in the file was modified.
- bound the container readiness poll in `run_tests.sh`. The loop that waits for a freshly started Uptime Kuma container to answer had neither an attempt cap nor a wall-clock deadline, so a container that never became ready — a bad image tag, an already-bound port, a container that exits on startup — left the script spinning on a half-second `curl` forever instead of failing, and left the container running too, because the `docker stop` further down was only reached once the loop exited. The poll now has a 60-second deadline, overridable via `READINESS_TIMEOUT`; each probe is capped with `curl --max-time 1` so a hung connect cannot stretch the interval; and on timeout the script reports which version it was waiting for and for how long, stops the container, and exits non-zero. Development tooling only: `run_tests.sh` drives the inherited integration suite against throwaway containers, is not invoked by CI, and is not part of the published distribution — no released artifact and no library behaviour is affected. Reported in [#15](https://github.com/pbarone/uptime-kuma-api2/issues/15) (credit: @JasonColapietro, PR [#20](https://github.com/pbarone/uptime-kuma-api2/pull/20) — the first outside contribution to this project).

### Release 2.3.0

Seven confirmed library defects, plus a documentation and provider-metadata sweep. Five are inherited from the original tracker; the other two were found by this project's own live verification, and they differ in provenance: on Uptime Kuma 2.x the cached monitor list went stale after every monitor mutation (found during pre-release verification against server 2.4.0), which is present in the original library identically — it registers no handler for either monitor-list delta either; and on **every Uptime Kuma 1.x server `add_monitor()` failed outright** because the 2.x-only `conditions` field was sent ungated (found while verifying that first fix against a 1.23.2 server), which is this project's own regression rather than an inherited one — introduced by `70138bf feat: add Uptime Kuma v2 support` and shipped in v2.1.0, v2.2.0 and v2.2.1, in code the original library never had, since it has no `conditions` monitor field at all. No new public API surface: every change is corrective or additive. The 2.x cache fix added and changed no version gating; the 1.x fix adds gating to eight monitor fields that had none, and leaves every gate that already existed exactly as it was; the five inherited fixes change no gating at all. The reports and pull requests credited below were all filed against the original [lucasheld/uptime-kuma-api](https://github.com/lucasheld/uptime-kuma-api), and cover the five inherited defects; the two found here have no upstream issue number.

#### Bugfixes
- `add_monitor()` works again on Uptime Kuma 1.x. Every call against a 1.x server failed with ``UptimeKumaException: insert into `monitor` (... `conditions` ...) - SQLITE_ERROR: table monitor has no column named conditions``, and no monitor was created. `conditions` is a 2.x-only monitor field, but `_build_monitor_data` assigned it in the unconditional common `data` dict rather than in the `>= 2.0` block that already gates every other v2-only field, so the key was emitted with its `[]` default on every call — **no caller opt-in of any kind was required**, which made the library's most-used public method unusable on v1 rather than merely limited. This is a fix to a **released regression, present in v2.1.0, v2.2.0 and v2.2.1** (introduced by `70138bf feat: add Uptime Kuma v2 support`, confirmed with `git tag --contains 70138bf`), not to an unreleased defect. The assignment now lives inside the existing `>= 2.0` block, so a v1 payload carries no `conditions` key at all, while v2 payloads are byte-identical to before — the `[]` default still present when the argument is absent, and an explicitly supplied list still passed through as the caller's own object with no reallocation and no per-condition validation. Seven adjacent v2-only fields that were likewise emitted outside the gate are now gated in place: `jsonPathOperator`, `snmp_v3_username`, `ping_count`, `ping_numeric`, `ping_per_request_timeout`, `mqttWebsocketPath` and `mqttCheckType`. Their `ValueError` argument validation still fires on both server majors, because a bad value is a bad value regardless of server version. No public method, parameter, class or export was added — the version guard is a private helper, and a new exception message is not API surface. No upstream issue number: discovered here, during the v1 compatibility run for the monitor-list cache fix below.
- `get_monitors()` no longer returns session-stale data on Uptime Kuma 2.x, and `delete_monitor` no longer raises `UptimeKumaException: monitor does not exist` for a monitor created moments earlier in the same session. 2.x stopped broadcasting the full monitor list after a mutation and now emits two deltas instead — `sendUpdateMonitorIntoList` -> `updateMonitorIntoList` (a `{id: monitor}` payload, after add, edit, pause, resume and the monitor tag operations) and `sendDeleteMonitorFromList` -> `deleteMonitorFromList` (the id alone, after a delete), both defined in `server/uptime-kuma-server.js`; `server/client.js` has no `sendMonitorList` at all, while `sendNotificationList`, `sendProxyList`, `sendAPIKeyList` and `sendDockerHostList` are all still there. The library registered no handler for either delta, so the packets were dropped on the floor and the cache never moved after login. The fix has two halves: handlers for both delta events keep the cache coherent after every mutation, and the two methods whose existence guard *reads* that cache — `delete_monitor` and `delete_monitor_tag` — now force a full-list refresh before the guard evaluates, so they decide on fresh data rather than on event ordering. The refresh costs one extra `getMonitorList` round trip (2-6ms observed) per guarded delete; nothing else gained a round trip. The failure reproduced with an `int` id, which is what distinguishes it from the string-id coercion defect fixed by its own entry in this same release ([lucasheld/uptime-kuma-api#91](https://github.com/lucasheld/uptime-kuma-api/issues/91)). No public method, parameter, class or export was added, and `get_monitors()` / `get_monitor()` return the same shapes as before. No upstream issue number: discovered here.
- all seven `delete_*` methods now accept a string id. `delete_monitor("371")` raised `UptimeKumaException: monitor does not exist` for a monitor that demonstrably existed, because the existence guard compared the caller's string against the server's integer ids (`if id_ not in [i["id"] for i in ...]`). The id is now coerced to `int` before the membership test and the coerced value is sent to the server, at all seven affected sites: `delete_monitor`, `delete_notification`, `delete_proxy`, `delete_tag`, `delete_docker_host`, `delete_maintenance` and `delete_api_key`. An id that genuinely does not exist still raises the same `"... does not exist"` exception and sends nothing to the server; a non-numeric value passes through the coercion untouched. Reported in [lucasheld/uptime-kuma-api#91](https://github.com/lucasheld/uptime-kuma-api/issues/91) (credit: @ausebiblibre, PR #92).
- `get_status_page` now honours `ssl_verify`. The constructor passed `ssl_verify` only to `socketio.Client` and never stored it, so the `requests.get` that fetches the public status page JSON sent no `verify=` argument and always verified the certificate. `ssl_verify` is now stored on the instance and forwarded as `verify=self.ssl_verify`, so an `ssl_verify=False` caller can read a status page from a server with a self-signed certificate. The default remains `True` for both the socket.io connection and the HTTP call, and the returned status page structure is unchanged. Reported in [lucasheld/uptime-kuma-api#65](https://github.com/lucasheld/uptime-kuma-api/issues/65) (credit: @pr0kium, PR #81).
- `add_monitor_tag` and `delete_monitor_tag` no longer raise `TypeError: 'NoneType' object does not support item assignment`. Both write the freshly fetched monitor into the cached monitor list, which is `None` until a monitor list event has arrived, so a tag operation before that point failed *after* the tag had already been changed on the server. The cache is now initialised first, mirroring the pattern used in `add_status_page`. An already-populated cache is updated exactly as before. Reported in [lucasheld/uptime-kuma-api#68](https://github.com/lucasheld/uptime-kuma-api/issues/68).
- non-PEP440 server versions no longer crash every version gate. A server reporting a string such as `2.0.0-dev-nightly-20240101` made `packaging.version.parse` raise `InvalidVersion` at each of the roughly ten `parse_version(self.version)` gate sites, breaking operations that are otherwise supported. Version parsing now runs through a single private accessor that returns a max sentinel (`9999`) when the string is unparseable, treating an unrecognised build as the newest version so all `>=` gates evaluate `True`. Valid versions parse exactly as before, so v1.x versus v2.x gating is bit-for-bit identical. Reported in [lucasheld/uptime-kuma-api#74](https://github.com/lucasheld/uptime-kuma-api/issues/74).
- socket.io timeouts now raise the library's own `Timeout`. `_call` let `socketio.exceptions.TimeoutError` escape, so callers catching `Timeout` or `UptimeKumaException` did not catch a timed-out call, even though `get_status_page` already translated its `requests` timeout. `_call` now catches only `socketio.exceptions.TimeoutError` and re-raises `Timeout` (a subclass of `UptimeKumaException`); `SocketIOError` and every other transport error still propagate unchanged, and successful calls return the same `{"ok": ...}`-unwrapped result. Reported in [lucasheld/uptime-kuma-api#44](https://github.com/lucasheld/uptime-kuma-api/issues/44).

#### Notes
- **Explicitly asking for `conditions` on a pre-2.0 server raises; the seven adjacent v2-only fields are dropped silently. The split is deliberate, and a caller cannot derive it from first principles, so it is stated here.** Passing a non-empty `conditions` list to `add_monitor` or `edit_monitor` against a server older than 2.0 now raises `UptimeKumaException: conditions requires Uptime Kuma 2.0 or newer, but the server reports version <observed>`, before any server call is made — and identically whether the value came from a keyword argument or from `MonitorBuilder.conditions()`, since the builder holds no connection and is enforced at the `add_monitor` / `edit_monitor` boundary instead. `conditions` raises because it defines the monitor's **up/down semantics**: silently discarding it produces a monitor that was created successfully and then reports success against criteria the caller never set, with no signal in the return value and none at check time. The other seven change *how* a check runs, not its verdict — a dropped `bearer_token` or `ipFamily` fails observably — so they are omitted silently, which is also what the `>= 2.0` block they join has always done for `ipFamily`, `cacheBust`, `subtype` and the rest. Two further reasons not to raise for those seven: they are explicit-opt-in-only, so none of them carries the unconditional total-outage property that makes `conditions` urgent, and whether each actually fails on v1 is unverified, so raising would convert a possibly-working path into a guaranteed hard error. An explicit `conditions=[]` is treated as "no conditions requested" and simply omitted on v1 rather than rejected; the guard tests truthiness, not `is not None`. Type validation still comes first: a non-list `conditions` raises `TypeError("conditions must be a list or None")` on both majors, ahead of any version handling.
- **Two earlier specs' assertions are narrowed by this fix, and both are annotated in place so neither reads as still-current.** `.kiro/specs/uptime-kuma-v2-support/design.md` *Property 1: Default conditions is empty list* asserted unconditional presence — correct only for v2, and now restricted to server versions >= 2.0 (Properties 3 and 4 in that document assert presence the same way and are narrowed with it). `.kiro/specs/uptime-kuma-v2-support-backlog/requirements.md` requirement 13.3 ("omit those parameters from the payload without raising an error or logging a warning") remains the rule for the seven adjacent fields but is narrowed for `conditions`, which raises; the severity argument is in `.kiro/specs/conditions-field-v1-regression/design.md` under `## Cross-Spec Policy Conflict`. Recorded as a deliberate retraction rather than left implicit, because a contributor reading either assertion as blanket would revert this fix.
- **Two follow-ups are noted here and designed nowhere.** (1) A uniform, library-wide signal for "your v2-only field was dropped", applied to every gated field rather than bolted onto one. That would let the `conditions` raise be retired and restore a single predictable rule; until it exists the library's treatment of v2-only monitor params is inconsistent by design, and this note is what makes that temporary and tracked rather than permanent and accidental. (2) The monitor **types** `RABBITMQ`, `SNMP`, `SMTP` and `SYSTEM_SERVICE` are themselves v2-only and are not version-gated, so requesting one against a v1 server sends a type the server does not know — the same defect class one level up. Out of scope in this release. ~~and it fails loudly rather than silently, which is why it is a note and not a fix.~~ **Superseded: fixed under `### Unreleased`.** That parenthetical was wrong on the mechanism, and the correction is why it became a fix: a 1.x server does not validate the monitor type when a monitor is added, so the loud failure was a `SQLITE_ERROR` on the type's *companion column* rather than a verdict on the type — and with those columns gated it would have become silent, not loud. Struck through rather than deleted, so this release's reasoning stays on the record as it was made.
- **The fix is unconditional on purpose, and that is the v1.x-friendlier choice rather than a shortcut.** The two delta handlers are inert on v1.x because v1.x never emits `updateMonitorIntoList` or `deleteMonitorFromList`; 1.23.X calls `sendMonitorList` after `add`, `editMonitor`, `pauseMonitor`, `resumeMonitor` and `deleteMonitor` alike, so the full-list broadcast keeps driving the cache there exactly as it did before. The guard refresh is likewise ungated because `socket.on("getMonitorList")` exists in both 1.23.X and 2.x, so the call is valid on either server. Gating it would be actively worse: reading `self.version` routes through `info()` -> `_get_event_data`, which pays an unconditional 0.2s `wait_events` sleep — tens of times the 2-6ms round trip the gate would be saving on v1.x. No `self.version`, `_parsed_version()` or `info()` lookup was introduced on any monitor path.
- **`pause_monitor` and `resume_monitor` needed no change, and were deliberately left alone.** Both server handlers emit `updateMonitorIntoList` before they ack, so the new delta handler has already written the updated `active` value by the time `_call` returns, and neither method reads the cache to decide anything. Separately, the six unrelated `delete_*` guards — notifications, proxies, docker hosts, API keys, tags and status pages — are untouched for a different reason: 2.x still broadcasts a full list for each of those resources, so their caches were never stale to begin with.
- **`wait_for_event` was documented, not changed.** It waits only for the *first* event of a given type and never resets the cached entry, so it is a no-op once the entry is populated — which is why the four `wait_for_event(Event.MONITOR_LIST)` wraps could not have waited for a refresh even in principle. Its signature and runtime behaviour are unchanged; the misleading one-line comment is now a comment block stating the semantics plainly and pointing callers who need fresh data at the refresh helper. A docstring would have published an internal-by-convention context manager in the API reference, so this stays a comment.
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
- extend `tests/test_monitor_params_v2.py` with 25 tests in four new classes for the `conditions` gate: implicit omission on v1 across monitor types, the `UptimeKumaException` for an explicit list via `_build_monitor_data`, `edit_monitor` and `MonitorBuilder` (message asserted to name the field, `2.0` and the observed version, and asserted to raise before `get_monitor` or `_call` is reached), v2 presence and `assertIs` list-identity passthrough, `TypeError` precedence over the version guard on both majors, the seven adjacent fields absent-and-silent on v1 with their `ValueError` validation still firing, and seeded generated-input cases over PEP440 versions, monitor types and condition-list shapes. The bug-condition tests were confirmed to fail against the pre-fix code — the omission tests with `conditions: []` in the v1 payload, the rejection tests with no exception raised at all — and no pre-existing class in the file was edited.
- add a `< 2.0` skip guard to `tests/test_monitor.py::test_monitor_type_dns`, which passes an explicit `conditions` list but, unlike its `test_monitor_conditions` and `test_monitor_dns_conditions` siblings, had none. Inherited integration suite, not CI; the test was red on v1 before this fix too.
- add `tests/live_test_conditions_v1.py`: manual v1 verification against a **disposable** Uptime Kuma 1.23.x container, which it bootstraps itself via `need_setup()` / `setup()` / `login()`. It reads its own `UPTIME_KUMA_V1_URL` / `UPTIME_KUMA_V1_USERNAME` / `UPTIME_KUMA_V1_PASSWORD` keys rather than the 2.x keys in `tests/.env`, refuses to run with the URL unset, and aborts unless the server reports `1.23`, so it cannot be mistargeted at the 2.x instance. `live_test_`-prefixed, so pytest never collects it and CI is unaffected.
- add `tests/test_monitor_cache_v2.py`: 35 tests covering the two delta handlers (merge, multi-entry payloads, post-edit and post-pause values, `None`-cache initialisation, int and string id coercion, absent-id no-ops, the zero-monitor sentinel, and copy-then-rebind rather than in-place mutation), both refreshed guards, and seeded generated-input cases for cache coherence, guard correctness across id sets and sentinel invariance. The two guard tests were confirmed to fail against the pre-fix code with the production exceptions (`monitor does not exist` / `monitor tag does not exist`) and with no delete sent.
- remove the temporary scaffolding from `tests/live_test_delete_id.py` — the three `api._call("getMonitorList")` workarounds, the staleness probe and its `known_issue()` reporting, and the `TEMPORARY SCAFFOLDING` block in the module docstring. The script's green run no longer depends on working around the library.
- add `tests/test_delete_id_coercion_v2.py`: 7 tests covering string id deletion at all seven `delete_*` sites, identical resolution for int and string ids, and absent ids of either type still raising and sending no delete
- extend the existing v2 unit files with 47 further regression tests: `test_status_page_v2.py` (`ssl_verify` forwarding and status page shape preservation), `test_monitor_params_v2.py` (monitor tag cache with a `None` and a populated cache, and version gate equivalence for valid, nightly and garbage version strings), `test_logger.py` (`_call` timeout translation plus non-timeout error and success pass-through), `test_notification_v2.py` (docstring examples, metadata types, and unchanged effective payloads). Every bug condition test was confirmed to fail against the pre-fix code.
- run `tests/test_status_page_incidents.py` in CI. It was added in 2.2.1 and documented as part of the unit suite, but was never listed in the GitHub Actions workflow, so its 10 tests had not actually been running.
- declare `python-dotenv` in `dev-requirements.txt`. Every `tests/live_test_*.py` script imports it, but it was declared nowhere, so a fresh clone could not run any of them. Development dependency only: the library itself does not import it and `install_requires` is unchanged.
- `tests/test_delete_id_coercion_v2.py` passes unmodified, including its `_call.assert_called_once_with("deleteMonitor", 371)` assertions: the refresh lives in a stubbable private helper rather than an inline second `_call`.

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
