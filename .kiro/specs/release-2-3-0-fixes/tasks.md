# Implementation Plan

## Overview

Six independent bug fixes for the 2.3.0 batch. Every fix follows the project's
test-first discipline: write a regression test, prove it fails (red) against the
UNFIXED code, apply the targeted fix, confirm it passes (green), and confirm the
paired preservation test still passes. Property numbers below match the
Correctness Properties in `design.md` (odd = fix/bug-condition, even =
preservation): Bug A → 1/2, Bug B → 3/4, Bug C → 5/6, Bug D → 7/8, Bug E → 9/10,
Bug F → 11/12.

## Tasks

### Bug A — string/int id guard across seven `delete_*` sites (#91)

- [x] 1. Write Bug A bug-condition exploration test (new file `tests/test_delete_id_coercion_v2.py`)
  - **Property 1: Bug Condition** - String-id delete of an existing entity
  - **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the type-blind membership guard exists.
  - **DO NOT attempt to fix the test or the code when it fails.**
  - **NOTE**: This test encodes the expected behavior — it will validate the fix when it passes after implementation.
  - **GOAL**: Surface counterexamples that demonstrate the bug at each of the seven sites.
  - **Scoped PBT approach**: Parametrize the property over all seven `delete_*` sites (monitor, notification, proxy, tag, docker host, maintenance, api key); for each, mock the entity accessor (`get_monitors`/`get_notifications`/`get_proxies`/`get_tags`/`get_docker_hosts`/`get_maintenances`/`get_api_keys`) to return an existing integer id (e.g. `371`) and mock `_call`.
  - Assert: calling `delete_*("371")` (numeric string) sends the delete to the server via `_call` and does NOT raise `UptimeKumaException`.
  - Run on UNFIXED code — **EXPECTED OUTCOME: Test FAILS** (unfixed raises `"... does not exist"` because `"371" not in [371]`).
  - Document the counterexample per site (e.g. `delete_monitor("371")` raises instead of deleting).
  - Mark complete when the test is written, run, and the red failure is documented.
  - _Bug_Condition: isBugCondition_A(site, id_) — entityExists(site, int(id_)) AND id_ NOT IN storedIds(site)_
  - _Requirements: 1.1, 1.2, 2.1, 2.2_

- [x] 2. Write Bug A preservation property test (in `tests/test_delete_id_coercion_v2.py`)
  - **Property 2: Preservation** - Int ids still delete, absent ids still raise
  - **IMPORTANT**: Follow observation-first methodology — observe behavior on UNFIXED code, then encode it.
  - Observe/assert: `delete_*(371)` (int) for an existing entity sends the delete via `_call` (unchanged).
  - Observe/assert: `delete_*("999")` and `delete_*(999)` for an absent id raise `UptimeKumaException("... does not exist")` and send NO delete.
  - **PBT**: generate random int and numeric-string ids (present and absent) across the seven sites; assert delete-for-existing, raise-for-absent regardless of caller type.
  - Run on UNFIXED code — **EXPECTED OUTCOME: Tests PASS** (this is the baseline to preserve).
  - _Preservation: for ¬isBugCondition_A, F(X) = F'(X)_
  - _Requirements: 2.3, 3.1, 3.2_

- [x] 3. Fix Bug A — generalise the id guard across all seven sites

  - [x] 3.1 Coerce the id at every `delete_*` guard in `uptime_kuma_api/api.py`
    - Apply one consistent pattern at `delete_monitor` (~1558), `delete_notification` (~1966), `delete_proxy` (~2128), `delete_tag` (~2938), `delete_docker_host` (~3533), `delete_maintenance` (~3895), `delete_api_key` (~4208).
    - Resolve the id list, then `try: id_ = int(id_) except (TypeError, ValueError): pass` so non-numeric strings fall through to the existing `"... does not exist"` raise (no `ValueError` leak).
    - Send the coerced (integer) `id_` to `_call` so the server receives the type it expects.
    - Keep each site inside its existing `with self.wait_for_event(...)` block and existing accessor. Do NOT touch the slug-keyed `delete_status_page` (out of scope).
    - _Bug_Condition: isBugCondition_A from design_
    - _Expected_Behavior: type-coerced membership check finds the entity; coerced id sent; no exception_
    - _Preservation: absent ids still raise; int-id path unchanged_
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2_

  - [x] 3.2 Verify Bug A exploration test now passes
    - **Property 1: Expected Behavior** - String-id delete of an existing entity
    - **IMPORTANT**: Re-run the SAME test from task 1 — do NOT write a new test.
    - **EXPECTED OUTCOME: Test PASSES** (confirms the string-id path deletes correctly at all seven sites).
    - _Requirements: 2.1, 2.2_

  - [x] 3.3 Verify Bug A preservation test still passes
    - **Property 2: Preservation** - Int ids still delete, absent ids still raise
    - **IMPORTANT**: Re-run the SAME test from task 2 — do NOT write new tests.
    - **EXPECTED OUTCOME: Tests PASS** (no regressions).
    - _Requirements: 2.3, 3.1, 3.2_

- [x] 4. Wire the new test file into the CI unit-suite command
  - The new file `tests/test_delete_id_coercion_v2.py` is NOT in the fixed CI list, so it will not run in CI until added. Append it to the explicit `pytest` command in ALL of:
    - `.github/workflows/test.yml`
    - `AGENTS.md`
    - `.kiro/steering/tech.md` (Key commands)
  - Keep the exact file list ordering consistent across the three locations.
  - Do NOT change the command to bare `pytest tests/` (that wipes live data).
  - _Requirements: 2.1, 2.2 (ensures Bug A regression coverage actually runs in CI)_

### Bug B — `ssl_verify` ignored by `get_status_page` (#65)

- [x] 5. Write Bug B bug-condition exploration test (`tests/test_status_page_v2.py`)
  - **Property 3: Bug Condition** - `verify` forwarded when `ssl_verify=False`
  - **CRITICAL**: This test MUST FAIL on unfixed code.
  - **DO NOT attempt to fix the test or the code when it fails.**
  - Construct `UptimeKumaApi(url, ssl_verify=False)` (patch `socketio.Client`/`connect`), patch `requests.get` to a mock, call `get_status_page("slug")`.
  - Assert `requests.get` was called with `verify=False`.
  - Run on UNFIXED code — **EXPECTED OUTCOME: Test FAILS** (unfixed omits any `verify=` kwarg; `self.ssl_verify` does not exist).
  - Document the counterexample (missing `verify=`).
  - _Bug_Condition: isBugCondition_B(X) — X.performsRequestsGet AND X.ssl_verify = False_
  - _Requirements: 1.3, 1.4, 2.4, 2.5_

- [x] 6. Write Bug B preservation test (`tests/test_status_page_v2.py`)
  - **Property 4: Preservation** - Default still verifies, return shape unchanged
  - **IMPORTANT**: Observe behavior on UNFIXED code first, then encode.
  - Assert: default `ssl_verify=True` path — the returned status-page dict has the same structure and fields as before (including the `incident`/`incidents` dual-key shape).
  - Run on UNFIXED code — **EXPECTED OUTCOME: Test PASSES** (baseline shape). Note: the `verify=True` assertion becomes meaningful only after the fix; the shape assertion is the preservation baseline here.
  - _Preservation: for ¬isBugCondition_B, F(X) = F'(X)_
  - _Requirements: 3.3, 3.4_

- [x] 7. Fix Bug B — store and forward `ssl_verify`

  - [x] 7.1 Store the flag and forward it to `requests.get` in `uptime_kuma_api/api.py`
    - In `__init__` (~483), add `self.ssl_verify = ssl_verify` before building `sio_kwargs`; keep passing it into `socketio.Client` unchanged.
    - In `get_status_page` (`requests.get` ~2237), add `verify=self.ssl_verify`, leaving `timeout=self.timeout` and the existing `Timeout` translation intact.
    - _Bug_Condition: isBugCondition_B from design_
    - _Expected_Behavior: requests.get called with verify=False when ssl_verify=False_
    - _Preservation: default verify=True; identical return dict shape_
    - _Requirements: 2.4, 2.5, 3.3, 3.4_

  - [x] 7.2 Verify Bug B exploration test now passes
    - **Property 3: Expected Behavior** - `verify` forwarded when `ssl_verify=False`
    - Re-run the SAME test from task 5. **EXPECTED OUTCOME: Test PASSES.**
    - _Requirements: 2.4, 2.5_

  - [x] 7.3 Verify Bug B preservation test still passes (and assert `verify=True` on default)
    - **Property 4: Preservation** - Default still verifies, return shape unchanged
    - Re-run the SAME test from task 6; additionally confirm the default path forwards `verify=True`. **EXPECTED OUTCOME: Tests PASS.**
    - _Requirements: 3.3, 3.4_

### Bug C — monitor-list cache write crash on `None` cache (#68)

- [x] 8. Write Bug C bug-condition exploration test (`tests/test_monitor_params_v2.py`)
  - **Property 5: Bug Condition** - No crash when `_event_data[MONITOR_LIST]` is `None`
  - **CRITICAL**: This test MUST FAIL on unfixed code.
  - **DO NOT attempt to fix the test or the code when it fails.**
  - Force `self._event_data[Event.MONITOR_LIST] = None`; mock `_call` and `get_monitor`; call `add_monitor_tag(...)` and `delete_monitor_tag(...)`.
  - Assert neither call raises `TypeError`.
  - Run on UNFIXED code — **EXPECTED OUTCOME: Test FAILS** with `TypeError: 'NoneType' object does not support item assignment`.
  - Document the counterexample.
  - _Bug_Condition: isBugCondition_C(op, cacheState) — cacheState[MONITOR_LIST] = None_
  - _Requirements: 1.5, 2.6_

- [x] 9. Write Bug C preservation test (`tests/test_monitor_params_v2.py`)
  - **Property 6: Preservation** - Populated cache behaves identically
  - **IMPORTANT**: Observe UNFIXED behavior first, then encode.
  - With `_event_data[MONITOR_LIST]` already populated, assert `add_monitor_tag`/`delete_monitor_tag` update the cache entry and return the server response exactly as before.
  - Run on UNFIXED code — **EXPECTED OUTCOME: Test PASSES.**
  - _Preservation: for ¬isBugCondition_C, F(X) = F'(X)_
  - _Requirements: 3.5_

- [x] 10. Fix Bug C — guard the monitor-list cache write

  - [x] 10.1 Add the None-guard in `add_monitor_tag` and `delete_monitor_tag` (`uptime_kuma_api/api.py`)
    - Before the `self._event_data[Event.MONITOR_LIST][str(monitor_id)] = ...` assignment in each method (~1740, ~1783), mirror the `add_status_page` pattern: `if self._event_data[Event.MONITOR_LIST] is None: self._event_data[Event.MONITOR_LIST] = {}`.
    - No other logic changes; leave the populated-cache path untouched.
    - _Bug_Condition: isBugCondition_C from design_
    - _Expected_Behavior: cache initialised then written; no TypeError_
    - _Preservation: populated-cache path unchanged_
    - _Requirements: 2.6, 3.5_

  - [x] 10.2 Verify Bug C exploration test now passes
    - **Property 5: Expected Behavior** - No crash when cache is `None`
    - Re-run the SAME test from task 8. **EXPECTED OUTCOME: Test PASSES.**
    - _Requirements: 2.6_

  - [x] 10.3 Verify Bug C preservation test still passes
    - **Property 6: Preservation** - Populated cache behaves identically
    - Re-run the SAME test from task 9. **EXPECTED OUTCOME: Test PASSES.**
    - _Requirements: 3.5_

### Bug D — non-PEP440 server versions crash version gates (#74)

- [x] 11. Write Bug D bug-condition exploration test (`tests/test_monitor_params_v2.py`)
  - **Property 7: Bug Condition** - Unparseable version treated as newest, never raises
  - **CRITICAL**: This test MUST FAIL on unfixed code.
  - **DO NOT attempt to fix the test or the code when it fails.**
  - Mock `version` (or `info()`) to return a nightly string (`"2.0.0-dev-nightly-20240101"`) and a garbage string (`"not-a-version"`); invoke a version-gated code path (or the new `_parsed_version()` choke point once it exists — for the red run, drive the raw `parse_version(self.version)` gate).
  - Assert the gate evaluates without raising and compares as newest (all `>=` gates True).
  - Run on UNFIXED code — **EXPECTED OUTCOME: Test FAILS** with `InvalidVersion`.
  - Document the counterexample.
  - _Bug_Condition: isBugCondition_D(X) — NOT isPep440Parseable(X)_
  - _Requirements: 1.6, 1.7, 2.7, 2.8_

- [x] 12. Write Bug D preservation property test (`tests/test_monitor_params_v2.py`)
  - **Property 8: Preservation** - Valid versions gate exactly as before; `version` still raw
  - **IMPORTANT**: Observe UNFIXED behavior first, then encode.
  - Assert: `"2.4.0"`, `"1.23.2"`, `"1.17.0"`, `"2.0"` gate identically to the original `parse_version(self.version)` comparison (v1/v2 boundary preserved).
  - Assert: the public `self.version` property still returns the raw server string unchanged.
  - **PBT**: generate valid PEP440 strings; assert the `_parsed_version()` gate result equals the original `parse_version(self.version)` gate result.
  - Run on UNFIXED code — **EXPECTED OUTCOME: Tests PASS** (baseline).
  - _Preservation: for ¬isBugCondition_D, F(X) = F'(X)_
  - _Requirements: 3.6_

- [x] 13. Fix Bug D — normalise version parsing behind one private choke point

  - [x] 13.1 Add `_parsed_version()` and replace the ~10 gate sites (`uptime_kuma_api/api.py`)
    - Add a private accessor: `try: return parse_version(self.version) except InvalidVersion: return parse_version("9999")` (treat unparseable as newest). Import `Version`/`InvalidVersion` from `packaging.version`; `parse` is already imported as `parse_version`.
    - Replace every `parse_version(self.version) >= parse_version("X.Y")` gate with `self._parsed_version() >= parse_version("X.Y")` at all ~10 sites.
    - **Judgment call (record in CHANGELOG):** the public `version` property is deliberately LEFT returning the raw server string; normalisation lives in the private `_parsed_version()` accessor so the public contract (Property 8 / 3.6) is untouched. Requirement 2.7 names "the version property" as the choke point; this design places it in a dedicated private accessor instead. "Newest" is realised with a max sentinel so all `>=` gates evaluate True.
    - Do NOT add public API surface.
    - _Bug_Condition: isBugCondition_D from design_
    - _Expected_Behavior: unparseable → newest sentinel; never raises InvalidVersion_
    - _Preservation: valid versions parse unchanged; version property still raw_
    - _Requirements: 2.7, 2.8, 3.6_

  - [x] 13.2 Verify Bug D exploration test now passes
    - **Property 7: Expected Behavior** - Unparseable version treated as newest, never raises
    - Re-run the SAME test from task 11 (pointing at `_parsed_version()` gates). **EXPECTED OUTCOME: Test PASSES.**
    - _Requirements: 2.7, 2.8_

  - [x] 13.3 Verify Bug D preservation test still passes
    - **Property 8: Preservation** - Valid versions gate exactly as before; `version` still raw
    - Re-run the SAME test from task 12. **EXPECTED OUTCOME: Tests PASS.**
    - _Requirements: 3.6_

### Bug E — socket.io timeout leaks wrong exception type (#44)

- [x] 14. Write Bug E bug-condition exploration test (`tests/test_logger.py`)
  - **Property 9: Bug Condition** - Timeout re-raised as library `Timeout`
  - **CRITICAL**: This test MUST FAIL on unfixed code.
  - **DO NOT attempt to fix the test or the code when it fails.**
  - `test_logger.py` already patches `socketio.Client`/`connect`; patch `sio.call` to raise `socketio.exceptions.TimeoutError`, then invoke a path through `_call`.
  - Assert the raised exception is the library `Timeout` (and `isinstance(err, UptimeKumaException)`).
  - Run on UNFIXED code — **EXPECTED OUTCOME: Test FAILS** (unfixed leaks `socketio.exceptions.TimeoutError`, not `Timeout`).
  - Document the counterexample.
  - _Bug_Condition: isBugCondition_E(X) — raises(X, socketio.exceptions.TimeoutError)_
  - _Requirements: 1.8, 2.9_

- [x] 15. Write Bug E preservation test (`tests/test_logger.py`)
  - **Property 10: Preservation** - Success and non-timeout errors unchanged
  - **IMPORTANT**: Observe UNFIXED behavior first, then encode.
  - Assert: a successful `_call` returns the same `{"ok"}`-unwrapped result as before.
  - Assert: a `_call` where `sio.call` raises a non-timeout error surfaces that error unchanged (only `TimeoutError` is translated).
  - Run on UNFIXED code — **EXPECTED OUTCOME: Tests PASS.**
  - _Preservation: for ¬isBugCondition_E, F(X) = F'(X)_
  - _Requirements: 3.7, 3.8_

- [x] 16. Fix Bug E — translate socket.io timeouts in `_call`

  - [x] 16.1 Wrap only the transport call in `_call` (`uptime_kuma_api/api.py` ~560)
    - `try: r = self.sio.call(event, data, timeout=self.timeout) except socketio.exceptions.TimeoutError as e: raise Timeout(e)`.
    - Leave the existing `{"ok"}` unwrapping and return path unchanged. Catch ONLY `TimeoutError`; non-timeout errors propagate unchanged. `Timeout` is already imported and subclasses `UptimeKumaException`.
    - _Bug_Condition: isBugCondition_E from design_
    - _Expected_Behavior: raises library Timeout (an UptimeKumaException)_
    - _Preservation: success result unchanged; non-timeout errors unchanged_
    - _Requirements: 2.9, 3.7, 3.8_

  - [x] 16.2 Verify Bug E exploration test now passes
    - **Property 9: Expected Behavior** - Timeout re-raised as library `Timeout`
    - Re-run the SAME test from task 14. **EXPECTED OUTCOME: Test PASSES.**
    - _Requirements: 2.9_

  - [x] 16.3 Verify Bug E preservation test still passes
    - **Property 10: Preservation** - Success and non-timeout errors unchanged
    - Re-run the SAME test from task 15. **EXPECTED OUTCOME: Tests PASS.**
    - _Requirements: 3.7, 3.8_

### Bug F — docs and metadata sweep (#78, #80, #60, #69, #57)

- [x] 17. Write Bug F bug-condition exploration/verification test (`tests/test_notification_v2.py`)
  - **Property 11: Bug Condition** - Examples run and metadata types are correct
  - **CRITICAL**: The metadata assertions MUST FAIL on unfixed code.
  - **DO NOT attempt to fix the test or the code when it fails.**
  - Metadata (#69, #57): assert the `SMTP` provider `smtpSecure` declared type is `"bool"`; assert the `notificationIDList` metadata declared default is `[]`. These FAIL on unfixed code (currently `"str"` and `{}`).
  - Docs (#78, #80): `exec` the `UptimeKumaApi` class docstring example; assert it runs without `NameError` (`MonitorType` import present) and that the shown `add_monitor` return key is `monitorID` (not `monitorId`). These FAIL on unfixed code (`NameError` / wrong casing).
  - Auth doc (#60/#73): assert the auth note text stating the UI "API key" cannot authenticate this socket.io API is present in the target docstring/README. Fails on unfixed code (absent).
  - Run on UNFIXED code — **EXPECTED OUTCOME: Test FAILS** on each defect. Document the counterexamples.
  - _Bug_Condition: isBugCondition_F(X) — exampleFailsToRun(X) OR metadataTypeIncorrect(X)_
  - _Requirements: 1.9, 1.10, 1.11, 1.12, 1.13, 2.10, 2.11, 2.12, 2.13, 2.14_

- [x] 18. Write Bug F preservation test (`tests/test_notification_v2.py`)
  - **Property 12: Preservation** - Runtime behaviour and shapes unchanged
  - **IMPORTANT**: Observe UNFIXED runtime behavior first, then encode — the sweep is behaviour-neutral.
  - Assert: the runtime conversion at `api.py` ~123 (`dict_notification_ids = {}`) still builds the `{id: True}` map — the effective `notificationIDList` payload for a monitor is unchanged (the `{}`→`[]` change is declared-type only).
  - Assert: accepted `smtpSecure` values are unchanged (the metadata type correction changes classification/docs, not accepted values).
  - Run on UNFIXED code — **EXPECTED OUTCOME: Tests PASS** (baseline to preserve).
  - _Preservation: for ¬isBugCondition_F, runtimeBehavior(F'(X)) = runtimeBehavior(F(X))_
  - _Requirements: 3.9, 3.10, 3.11_

- [x] 19. Fix Bug F — docs and metadata corrections

  - [x] 19.1 Fix the docstring examples in `uptime_kuma_api/api.py`
    - #78: change the shown imports to `from uptime_kuma_api import UptimeKumaApi, MonitorType` in both the `>>>` example (~424) and the context-manager `code-block` (~442).
    - #80: change `'monitorId': 1` to `'monitorID': 1` (~430) to match the real return key and the `add_monitor` docstring at ~1679.
    - Any touched docstring containing backslashes must remain/become a raw string (`r"""`) to avoid `SyntaxWarning` on 3.12+.
    - _Requirements: 2.10, 2.11, 3.9_

  - [x] 19.2 Add the auth-key documentation note (#60/#73)
    - Add a short note (auth-related docstring and/or README) stating the Uptime Kuma UI "API key" cannot authenticate this socket.io API (it is `/metrics`-only).
    - _Requirements: 2.12_

  - [x] 19.3 Correct provider metadata in `uptime_kuma_api/notification_providers.py`
    - #69: change `smtpSecure=dict(type="str", required=False)` to `type="bool"` in the `SMTP` provider table (verified against upstream `SMTP.vue`).
    - #57: locate the metadata declaration whose `notificationIDList` default is `{}` and change it to `[]`. **Reproduce-before-fixing applies:** the runtime conversion at `api.py` ~123 MUST NOT change (preserving 3.10). If the `{}` declared-type default is not present in the current tree, the fix is a verification no-op — record that this is declared-type only.
    - _Requirements: 2.13, 2.14, 3.10, 3.11_

  - [x] 19.4 Verify Bug F exploration test now passes
    - **Property 11: Expected Behavior** - Examples run and metadata types are correct
    - Re-run the SAME test from task 17. **EXPECTED OUTCOME: Test PASSES.**
    - _Requirements: 2.10, 2.11, 2.12, 2.13, 2.14_

  - [x] 19.5 Verify Bug F preservation test still passes
    - **Property 12: Preservation** - Runtime behaviour and shapes unchanged
    - Re-run the SAME test from task 18. **EXPECTED OUTCOME: Tests PASS.**
    - _Requirements: 3.9, 3.10, 3.11_

### Finalisation

- [x] 20. Update `CHANGELOG.md` for the user-facing fixes
  - Add entries (Conventional Commits style) for the user-facing defects: Bug A (#91 string/int id coercion in `delete_*`), Bug B (#65 `ssl_verify` honored by `get_status_page`), Bug C (#68 tag ops on empty monitor-list cache), Bug D (#74 non-PEP440 server versions no longer crash version gates), Bug E (#44 socket.io timeouts now raise the library `Timeout`).
  - Record the **Bug D judgment call**: the public `version` property intentionally still returns the raw server string; normalisation lives in the private `_parsed_version()` accessor, so no public contract changed.
  - Note the Bug F docs/metadata sweep (#78, #80, #60, #69, #57) as behaviour-neutral. Credit the original author and incorporated PR authors as applicable.
  - _Requirements: 2.1–2.14 (user-facing summary); 3.6 (version-property judgment call)_

- [x] 21. Checkpoint — run the CI unit suite and confirm all tests pass
  - Run EXACTLY (never bare `pytest tests/` — it wipes live data):
    ```
    pytest tests/test_monitor_types_v2.py tests/test_monitor_params_v2.py tests/test_status_page_v2.py tests/test_notification_v2.py tests/test_logger.py tests/test_monitor_builder.py tests/test_status_page_incidents.py tests/test_delete_id_coercion_v2.py -v
    ```
    (The trailing `tests/test_delete_id_coercion_v2.py` matches the CI list updated in task 4.)
  - Confirm all six exploration tests are green (bugs fixed) and all six preservation tests are green (no regressions). Ask the user if any question arises.
  - Confirm no new public API surface was added and v1.x backward compatibility is intact.
  - _Requirements: all_

## Notes

**Safety:** All regression tests live in the v2 unit files (no live server;
mock version/transport). NEVER run bare `pytest tests/` — the inherited
integration tests wipe all data on the target instance. Use only the explicit CI
file list.

### Task Dependency Graph

```
Bug A:  1 (red) ─┐
        2 (base)─┤
                 └─> 3.1 (fix) ─> 3.2 (green) ─> 3.3 (preserve) ─> 4 (CI wiring)
Bug B:  5 (red) ─┐
        6 (base)─┤
                 └─> 7.1 (fix) ─> 7.2 (green) ─> 7.3 (preserve)
Bug C:  8 (red) ─┐
        9 (base)─┤
                 └─> 10.1 (fix) ─> 10.2 (green) ─> 10.3 (preserve)
Bug D: 11 (red) ─┐
       12 (base)─┤
                 └─> 13.1 (fix) ─> 13.2 (green) ─> 13.3 (preserve)
Bug E: 14 (red) ─┐
       15 (base)─┤
                 └─> 16.1 (fix) ─> 16.2 (green) ─> 16.3 (preserve)
Bug F: 17 (red) ─┐
       18 (base)─┤
                 └─> 19.1/19.2/19.3 (fix) ─> 19.4 (green) ─> 19.5 (preserve)

Finalisation:
  {3.3, 7.3, 10.3, 13.3, 16.3, 19.5} ─> 20 (CHANGELOG)
  {4, all *.green, all *.preserve, 20} ─> 21 (CI checkpoint)
```

- The six bug tracks (A–F) are mutually independent and may be executed in any
  order or in parallel; within each track, red test → fix → green → preserve is
  strictly sequential.
- Task 4 (CI wiring) depends only on the new file existing (task 1) but is
  logically grouped after Bug A's fix; it MUST complete before task 21 so the
  new file runs in the checkpoint.
- Task 20 (CHANGELOG) depends on all fixes landing. Task 21 (final CI checkpoint)
  is the last task and depends on everything.
