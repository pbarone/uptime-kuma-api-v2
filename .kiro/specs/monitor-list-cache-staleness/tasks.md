# Implementation Plan

## Overview

On Uptime Kuma 2.x the cached monitor list goes stale after every monitor
mutation: the server stopped broadcasting the full `monitorList` and now emits
the deltas `updateMonitorIntoList` / `deleteMonitorFromList`, which this library
does not handle. The fix has two halves — add the two delta handlers so the cache
stays coherent, and add a deterministic `_refresh_monitor_list()` call inside the
two cache-reading guards (`delete_monitor`, `delete_monitor_tag`) so they decide
on fresh data instead of a stale snapshot.

Sequencing note: tasks 1 and 2 exist as separate steps on purpose. Requirement 2.9
demands regression tests *demonstrated* to fail against the unfixed code, and the design
identifies tests 14 and 15 as the only ones that constitute real evidence — they refer
only to names that exist pre-fix (`_event_data`, `_call`, `wait_events`, `timeout`) and
fail with the actual production exception rather than an `AttributeError`. Writing them
and recording their pre-fix failure output are therefore two distinct deliverables, and
neither may be folded into the implementation task.

Test command, used everywhere below (**never bare `pytest tests/`** — the inherited
integration tests wipe every monitor, notification, proxy, tag, status page, docker host,
maintenance and API key on the target instance):

```
pytest tests/test_monitor_types_v2.py tests/test_monitor_params_v2.py tests/test_status_page_v2.py tests/test_notification_v2.py tests/test_logger.py tests/test_monitor_builder.py tests/test_status_page_incidents.py tests/test_delete_id_coercion_v2.py tests/test_monitor_cache_v2.py -v
```

## Tasks

### Pre-fix evidence and preservation baseline

- [x] 1. Write the guard harness and the two bug-condition guard tests
  - **Property 1: Bug Condition** - Cache-reading guards decide on fresh data
  - **CRITICAL**: These tests MUST FAIL on unfixed code — the failure is the evidence requirement 2.9 asks for
  - **DO NOT** fix the tests or the code when they fail in task 2
  - **GOAL**: surface counterexamples proving a guard rejects an id the server demonstrably has
  - Create `tests/test_monitor_cache_v2.py` with the **guard harness** described in the design's Testing Strategy: a `MagicMock(spec=UptimeKumaApi)` with a real `_event_data` dict, real `wait_for_event`, `_get_event_data` and `get_monitors` bound via `UptimeKumaApi.<method>.__get__(api)`, `api.wait_events = 0` and a small `api.timeout`
  - Mock `_call` with a `side_effect` that mimics the server contract: a `getMonitorList` call **populates** `api._event_data[Event.MONITOR_LIST]` with the fresh string-keyed dict exactly as `_event_monitor_list` would; a `deleteMonitor` / `deleteMonitorTag` call returns a success dict
  - **The harness must reference only names that exist before the fix.** Do NOT bind or reference `_refresh_monitor_list`, `_event_update_monitor_into_list` or `_event_delete_monitor_from_list` in this harness — that is what lets the tests fail for the right reason instead of erroring on a missing attribute
  - Test 14 — `delete_monitor` sends `deleteMonitor` for an id present only **after** a refresh: seed the cache with a stale id set that omits the target, have the `getMonitorList` side effect supply a fresh set that includes it, assert `_call` is invoked with `("deleteMonitor", <id>)`
  - Test 15 — `delete_monitor_tag` sends `deleteMonitorTag` for a tag present only **after** a refresh: same shape, stale cache monitor entry carries no matching `(tag_id, monitor_id, value)` triple, the fresh one does
  - Both tests must exercise the **real guard bodies**, not a reimplementation of them
  - _Requirements: 1.2, 1.6, 2.2, 2.6, 2.9_

- [x] 2. Run tests 14 and 15 against the unfixed code and record the failure output
  - **Property 1: Bug Condition** - Cache-reading guards decide on fresh data
  - Run exactly: `pytest tests/test_monitor_cache_v2.py -v`
  - **EXPECTED OUTCOME**: both tests FAIL. Test 14 with `UptimeKumaException: monitor does not exist`; test 15 with `UptimeKumaException: monitor tag does not exist`. In both cases `_call` was never invoked with the delete
  - **Verify the failure reason**, not just the failure: the traceback must come from the guard raising, NOT from an `AttributeError` on a missing method. An `AttributeError` here means the harness leaked a post-fix name and task 1 needs correcting
  - Record the verbatim pytest output (test ids, exception type, exception message, and the `_call` assertion state) in the task notes or the PR description — this is the requirement 2.9 evidence artifact and the fix must not land without it
  - Do NOT implement anything in this task
  - Mark complete when both tests have been run, have failed with the production exceptions, and the output is recorded
  - _Requirements: 2.9_

- [x] 3. Write the preservation tests and verify they pass on the unfixed code
  - **Property 2: Preservation** - Everything outside a 2.x monitor mutation is untouched
  - **IMPORTANT**: observation-first — run each case against the UNFIXED code, observe the actual result, then encode that observed result as the assertion
  - Add to `tests/test_monitor_cache_v2.py`, using the guard harness from task 1 (still pre-fix-name-only)
  - Test 16 — `delete_monitor` with a genuinely absent id still raises `UptimeKumaException("monitor does not exist")` and sends no delete (3.3)
  - Test 17 — `delete_monitor("7")` for an existing monitor 7 still succeeds, and `delete_monitor("not-an-id")` still raises the library's own `UptimeKumaException`, never a leaked `ValueError` (3.4, the shipped #91 contract)
  - Test 18 — `delete_monitor_tag` with an absent tag still raises and sends nothing (3.3 tag analogue)
  - Test 20 — `wait_for_event(Event.MONITOR_LIST)` with an already-populated entry returns without waiting, documenting the no-op that task 4.4's comment will state (1.7, 2.7)
  - Sentinel preservation — `_get_event_data` with a `{}` monitor list still short-circuits to `[]` for all six monitor-scoped events: `avgPing`, `uptime`, `heartbeatList`, `importantHeartbeatList`, `certInfo`, `heartbeat` (3.5)
  - Monitor-tag cache patching — `add_monitor_tag` / `delete_monitor_tag` still write the target monitor under its **string** key (3.7)
  - v1.x inertness — a simulated v1.x full-list `monitorList` broadcast produces a byte-identical cache to today's, with no delta handler involved (3.1)
  - Run exactly: `pytest tests/test_monitor_cache_v2.py -v`
  - **EXPECTED OUTCOME**: every test in this task PASSES on the unfixed code (tests 14 and 15 still fail — that is correct). These passes are the baseline to preserve
  - Mark complete when written, run, and passing pre-fix
  - _Requirements: 3.1, 3.3, 3.4, 3.5, 3.7, 1.7, 2.7_

### The fix

- [x] 4. Fix the monitor list cache staleness on 2.x

  - [x] 4.1 Add the two delta events to `Event` (change group 1)
    - In `uptime_kuma_api/event.py`, add `UPDATE_MONITOR_INTO_LIST = "updateMonitorIntoList"` and `DELETE_MONITOR_FROM_LIST = "deleteMonitorFromList"` immediately after `MONITOR_LIST` so the three monitor-list events read as a group
    - **Do NOT add `_event_data` entries for either member.** They mutate the existing `MONITOR_LIST` entry rather than being waited on; entries would create two never-read cache slots and would make `wait_for_event(Event.UPDATE_MONITOR_INTO_LIST)` look supported when waiting for a delta is precisely the wrong thing to do. `wait_for_event` / `_get_event_data` raising `KeyError` for these members is the intended consequence
    - Additive only: no new method, parameter, class or export, and `Event` is not in `docs/api.rst`, so the published reference does not change
    - _Requirements: 2.1, 2.3, 3.8_

  - [x] 4.2 Add the two delta handlers and register them (change group 2)
    - In `uptime_kuma_api/api.py`, register directly after the existing `Event.MONITOR_LIST` line so registration order matches handler definition order
    - Define `_event_update_monitor_into_list(self, data)` and `_event_delete_monitor_from_list(self, monitor_id)` immediately after `_event_monitor_list`, per the design's code blocks
    - **Copy-then-rebind, never mutate in place**: build `updated = dict(monitors)` and assign it back. These are the first cache writers on the socket.io read-loop thread, so a reader copying the same dict must see either the old dict or the new one, never one mid-mutation
    - **`str()` key coercion on both sides, unconditionally**: no-op for `updateMonitorIntoList`'s already-string JSON keys, load-bearing for `deleteMonitorFromList`, which carries the raw `monitor.id` as an **int**
    - **Asymmetric `None`-cache handling, deliberately**: the update handler initialises `{}` and then populates it, so the result is never empty; the delete handler **returns early** rather than creating `{}`, because a fabricated `{}` would counterfeit the zero-monitor sentinel and short-circuit the monitor-scoped events to `[]` while monitors may well exist
    - Store the **raw server payload, unparsed** — `get_monitors()` / `get_monitor()` apply `_convert_monitor_return`, `int_to_bool` and the `parse_*` helpers on the way out; parsing here would double-parse and change return shapes
    - Carry over the design's explanatory comments, including the one stating v1.x never emits these events so both handlers are inert there
    - _Requirements: 1.1, 1.3, 1.4, 1.5, 2.1, 2.3, 2.4, 2.5, 3.5, 3.9_

  - [x] 4.3 Add `_refresh_monitor_list()` and call it from the two guards (change group 3)
    - Add the private helper immediately after `_call`, with the rest of the private plumbing and before the `# event handlers` block. Body is a single `self._call('getMonitorList')`
    - Include the design's comment block: why it is deterministic (the server emits `monitorList` and only then acks, socket.io delivers both in order on this connection, and the sync client dispatches events and acks on the same read-loop thread, so `_event_monitor_list` has already run when `sio.call` returns), and why it is deliberately **not** version gated (`getMonitorList` exists in 1.23.X and 2.x, and reading `self.version` would route through `info()` → `_get_event_data` and pay a 0.2 s `wait_events` sleep to save a 2-6 ms round trip)
    - Insert `self._refresh_monitor_list()` as the **first statement inside the existing `with self.wait_for_event(Event.MONITOR_LIST):`** in `delete_monitor` and in `delete_monitor_tag` — one line per guard, before the cache read, so the refreshed list is what the guard sees
    - **Keep it a stubbable helper, not two inline `self._call("getMonitorList")` lines.** An inline call would add a second `_call` and break the seven existing `api._call.assert_called_once_with("deleteMonitor", 371)` assertions in `tests/test_delete_id_coercion_v2.py` for no behavioural reason
    - Let exceptions propagate: a `Timeout` from the refresh surfaces as the library's own already-documented `Timeout`, and swallowing it would mean deciding the guard from data we just failed to refresh
    - **Do NOT modify `pause_monitor` or `resume_monitor`** — both server handlers emit `updateMonitorIntoList` before they ack, so the group 4.2 handler has already written the new `active` value by the time `_call` returns, and neither method reads the cache
    - **Do NOT remove the four `wait_for_event(Event.MONITOR_LIST)` wraps.** They are no-ops once the cache is populated but still block on a session's first mutation while the entry is `None`; removing them would change v1.x control flow on the fix path
    - **Do NOT touch the other six `delete_*` guards** (notifications, proxies, docker hosts, API keys, tags, status pages) — 2.x still broadcasts a full list for each
    - _Bug_Condition: `isBugCondition(input)` = `isCacheStaleCondition` OR `isStaleGuardCondition` from the design_
    - _Expected_Behavior: design Correctness Properties 1 and 3 — deltas keep the cache coherent, and guards decide on fresh data without consulting `self.version`_
    - _Preservation: design Preservation Requirements — v1.x untouched, no version lookup on monitor paths, six unrelated guards unmodified, sentinel intact, #91 contract intact_
    - _Requirements: 2.2, 2.6, 2.10, 3.2, 3.3, 3.6_

  - [x] 4.4 Document `wait_for_event`'s first-event-only semantics (change group 4)
    - Replace the single `# waits for the first event of the given type to arrive` comment on `wait_for_event` with a comment block stating plainly that it waits only for the **first** event of that type, that it never resets the cached entry, and that it is therefore a no-op once the entry is populated — so it cannot be used to wait for a *refresh*, and callers needing fresh data must fetch it (pointing at `_refresh_monitor_list`)
    - **A comment, not a docstring.** `docs/api.rst` autodocs `UptimeKumaApi`, so a docstring would newly publish this internal-by-convention context manager in the API reference as a supported helper
    - Signature and runtime behaviour unchanged, byte for byte
    - _Requirements: 1.7, 2.7_

  - [x] 4.5 Verify the bug-condition guard tests now pass
    - **Property 1: Expected Behavior** - Cache-reading guards decide on fresh data
    - **IMPORTANT**: re-run the SAME tests 14 and 15 from task 1 — do NOT write new tests and do NOT edit those tests
    - Run exactly: `pytest tests/test_monitor_cache_v2.py -v`
    - **EXPECTED OUTCOME**: tests 14 and 15 now PASS, confirming the guards send `deleteMonitor` / `deleteMonitorTag` for entities the server has
    - _Requirements: 1.2, 1.6, 2.2, 2.6_

  - [x] 4.6 Verify the preservation tests still pass
    - **Property 2: Preservation** - Everything outside a 2.x monitor mutation is untouched
    - **IMPORTANT**: re-run the SAME tests from task 3 — do NOT write new tests and do NOT relax any assertion
    - Run exactly: `pytest tests/test_monitor_cache_v2.py -v`
    - **EXPECTED OUTCOME**: every task-3 test still PASSES — absent ids still rejected, #91 string-id contract intact, sentinel still short-circuiting, tag cache still string-keyed, v1.x path unchanged, `wait_for_event` still a no-op on a populated entry
    - _Requirements: 3.1, 3.3, 3.4, 3.5, 3.7_

### Remaining unit tests

- [x] 5. Write the delta handler unit tests and the seeded generated-input tests

  - [x] 5.1 Add the handler harness and delta handler tests 1-12
    - **Property 3: Bug Condition** - Delta events keep the cached monitor list coherent
    - Add the **handler harness** to `tests/test_monitor_cache_v2.py`: a `MagicMock(spec=UptimeKumaApi)` with a real `_event_data` dict and the handler under test bound via `UptimeKumaApi._event_update_monitor_into_list.__get__(api)`, asserting on the cache dict directly
    - Test 1 — update handler merges a new id into a populated cache (1.1, 2.1)
    - Test 2 — update handler merges a multi-entry payload (2.1)
    - Test 3 — update handler replaces an existing entry with post-edit values (1.4, 2.4)
    - Test 4 — update handler reflects a changed `active` flag from pause/resume (1.5, 2.5)
    - Test 5 — update handler initialises a `None` cache without raising (2.1, 3.7)
    - Test 6 — update handler coerces int payload keys to `str` (2.1)
    - Test 7 — delete handler removes an entry given an **int** id (1.3, 2.3)
    - Test 8 — delete handler removes an entry given a **string** id (2.3)
    - Test 9 — delete handler on an absent id is a no-op, cache unchanged (2.3)
    - Test 10 — delete handler on a `None` cache leaves it `None`, never `{}` (3.5)
    - Test 11 — delete handler removing the last monitor leaves `{}`, and the sentinel still short-circuits to `[]` (3.5)
    - Test 12 — both handlers rebind rather than mutate a dict a reader may already hold: capture the pre-call dict object, assert it is unchanged and that `_event_data[Event.MONITOR_LIST]` is a different object (3.5, 3.9)
    - These are correctness tests for new code. They fail pre-fix only with `AttributeError`, which the design calls weak evidence — they are NOT the requirement 2.9 proof, task 2 is
    - _Requirements: 1.1, 1.3, 1.4, 1.5, 2.1, 2.3, 2.4, 2.5, 3.5, 3.9_

  - [x] 5.2 Add test 19 — `_refresh_monitor_list` issues one RPC and no version lookup
    - Assert `_refresh_monitor_list` calls `_call` exactly once with `"getMonitorList"`
    - Assert it touches no version accessor: no `self.version`, no `_parsed_version()`, no `info()` — this is the guard on requirement 3.2's cost argument
    - _Requirements: 2.10, 3.2_

  - [x] 5.3 Add the seeded generated-input tests
    - **Property 3: Bug Condition** - Delta events keep the cached monitor list coherent
    - Follow the seeded `random.Random` idiom already established by `generated_id_cases()` in `tests/test_delete_id_coercion_v2.py`. **Hypothesis is deliberately not a project dependency**; a fixed seed keeps CI reproducible
    - Cache-coherence round trip (test 13) — generate random cache states (empty, single, many monitors, string keys) and random delta payloads (int or string keys, one or many entries); assert the post-delta cache equals the expected merged/reduced dict, and that deleting everything just added returns the cache to its starting value (2.1, 2.3)
    - Guard correctness across id sets — generate `(stale_ids, fresh_ids, target_id)` triples; assert `delete_monitor` sends the delete for every target in `fresh_ids` regardless of `stale_ids`, and raises without sending for every target in neither, in both int and string forms (2.2, 3.3, 3.4)
    - **Property 4: Preservation** — sentinel invariance: across generated handler call sequences, assert the cache is never set back to `None` after having been populated, and that `{}` occurs only when the monitor count genuinely reached zero (3.5)
    - _Requirements: 2.1, 2.2, 2.3, 3.3, 3.4, 3.5_

- [x] 6. Verify `tests/test_delete_id_coercion_v2.py` still passes completely unmodified
  - **Property 2: Preservation** - The guards still reject what does not exist
  - Run exactly: `pytest tests/test_delete_id_coercion_v2.py -v`
  - **EXPECTED OUTCOME**: all tests pass with **zero edits to that file**. If a change is needed there, the fix is wrong — revisit task 4.3
  - Specifically confirm the seven `api._call.assert_called_once_with("deleteMonitor", 371)`-style assertions still hold: `_refresh_monitor_list` is stubbed out by `MagicMock(spec=UptimeKumaApi)`, so no second `_call` appears. This is the strongest preservation signal in the suite and it is free
  - If this file appears in the diff at all, stop and report it
  - _Requirements: 3.3, 3.4_

### Cleanup and bookkeeping

- [x] 7. Remove the temporary scaffolding from `tests/live_test_delete_id.py` (change group 5)
  - Delete exactly these eight items and nothing else:
    1. The whole `TEMPORARY SCAFFOLDING -- remove when the monitor-list cache defect is fixed:` section of the module docstring
    2. The Step 2 staleness probe: the `ids_before_refresh = ...` line through the `if monitor_id not in ids_before_refresh:` / `else:` block, including its `known_issue(...)` call, its `INFO` print, and the `--- KNOWN ISSUE probe ---` comment above it
    3. `api._call("getMonitorList")` #1 — Step 2, before the string-id delete — with its `WORKAROUND for the known cache defect` comment
    4. `api._call("getMonitorList")` #2 — Step 2, before the post-delete `get_monitors()` read — with its `Same WORKAROUND again` comment
    5. `api._call("getMonitorList")` #3 — the cleanup int-id fallback — with its `Same WORKAROUND as Step 2` comment
    6. The `known_issue()` helper function
    7. The module-level `known_issues = []` list
    8. The `if known_issues:` reporting block at the end of `main()`
  - **Explicitly keep**: the `skip()` helper, the whole Step 4 Bug E probe, `record()`, the `results` list and its reporting, the safety notes, and the ASCII-only output convention
  - This removal is only signed off by task 11, which runs the de-scaffolded script end to end. Until then treat it as unverified
  - _Requirements: 2.8_

- [x] 8. Write the changelog entry, compatibility argument and triage note (change group 6, docs half)
  - `CHANGELOG.md` — new `### Release 2.3.1` section above `### Release 2.3.0`, with `#### Bugfixes` and `#### Notes`
  - The bugfix entry states the 2.x behaviour change with its server-source citation (`sendUpdateMonitorIntoList` / `sendDeleteMonitorFromList` in `server/uptime-kuma-server.js`, no `sendMonitorList` in `server/client.js`), the two-halves fix, the one extra round trip per guarded delete, and that no public API surface changed
  - The notes entry carries the **written v1.x compatibility argument** in substance: the delta handlers are inert on v1.x because v1.x never emits `updateMonitorIntoList` or `deleteMonitorFromList` and instead keeps sending the full `monitorList` after every mutation; the guard refresh is unconditional because `socket.on("getMonitorList")` exists in both 1.23.X and 2.x, and gating it on `self.version` would route through `info()` → `_get_event_data` and pay a 0.2 s `wait_events` sleep to save a 2-6 ms RPC — so *not* gating is the v1-friendlier choice, not a shortcut. Also record the judgment call that `pause_monitor` / `resume_monitor` needed no change
  - Do **not** bump `uptime_kuma_api/__version__.py` — that is a release-time decision, not part of this fix
  - `UPSTREAM_TRIAGE.md` section 7 — append a short resolution note: which candidate route was taken (1 **and** 2 of the three listed), that `wait_for_event` was documented rather than changed and why, and that the `live_test_delete_id.py` scaffolding is gone. A few lines only; section 7's own preamble warns against duplicating the account
  - _Requirements: 2.9, 2.10_

- [x] 9. Update the unit-test file list in all five places in one change (change group 6, CI half)
  - Adding `tests/test_monitor_cache_v2.py` means the list must be updated everywhere it is spelled out. **All five land together or the change is incomplete** — this is deliberately one task so the places cannot drift apart, which has already bitten this project once (`test_status_page_incidents.py` was documented as part of the unit suite for a whole release while never actually running in CI)
    1. `.github/workflows/test.yml` (~line 28) — the only one that actually affects CI
    2. `CONTRIBUTING.md` (~line 35)
    3. `AGENTS.md` (~line 45)
    4. `.kiro/steering/tech.md` (~line 35)
    5. `.kiro/steering/structure.md` (~line 25) — the prose enumeration of the v2 suite
  - **`run_tests.sh` needs no change** — it carries no file list, running `python -m unittest discover -s tests` against a Docker instance, so discovery picks the new file up automatically
  - **Also de-number `.kiro/steering/testing.md`**: it says "the six v2 files" while there are already eight (nine after this change). Replace the count with wording that cannot drift again rather than re-counting it. Any other spelled-out count ("the 8-file CI list") becomes nine
  - Verify by grepping for `test_delete_id_coercion_v2` across the repo and confirming every hit that is a CI-list enumeration now also names `test_monitor_cache_v2.py`
  - _Requirements: 2.9_

### Verification

- [x] 10. Checkpoint - full unit suite green
  - Run exactly (**never bare `pytest tests/`**):
    ```
    pytest tests/test_monitor_types_v2.py tests/test_monitor_params_v2.py tests/test_status_page_v2.py tests/test_notification_v2.py tests/test_logger.py tests/test_monitor_builder.py tests/test_status_page_incidents.py tests/test_delete_id_coercion_v2.py tests/test_monitor_cache_v2.py -v
    ```
  - Confirm all 20 tests in `tests/test_monitor_cache_v2.py` pass, including the seeded generated-input tests
  - Confirm `tests/test_delete_id_coercion_v2.py` passes with no edits (task 6)
  - Confirm no other pre-existing v2 test regressed
  - Confirm no new public method, parameter, class or export was added, and that `docs/api.rst` is unchanged
  - Confirm no `self.version` / `_parsed_version()` / `info()` reference was introduced on any monitor path
  - **At this point the fix is unit-verified and can be considered complete.** Task 11 is additional manual confirmation and does not block this checkpoint. Ask the user if any question arises
  - _Requirements: 2.9, 3.2, 3.8_

- [x] 11. MANUAL — live verification against a disposable 2.x instance
  - **Not CI. Not automated. Requires a reachable, disposable Uptime Kuma 2.x instance configured via `tests/.env`.** Skip this task if no such instance is available; it does not block task 10's completion
  - **This task is what licenses the scaffolding removal in task 7.** Until it has been run green, treat task 7 as unverified
  - Run `tests/live_test_delete_id.py` with all scaffolding removed — the acceptance test for the whole fix: create a monitor, `get_monitors()` sees the new id with **no** `_call("getMonitorList")` workaround, string-id delete succeeds, the post-delete `get_monitors()` read sees it gone on the library's own behaviour, exit code 0
  - Run a pause/resume/edit round trip: mutate, then `get_monitors()` and confirm the post-mutation `active` value and the edited field values, with no refresh call — this proves the delta handler covers the two methods task 4.3 deliberately left unmodified (1.4, 1.5, 2.4, 2.5)
  - Run `tests/live_test_create.py`, then `tests/live_test_cleanup.py --dry-run`, then the real cleanup — confirms the monitor-tag paths and the six unrelated `delete_*` guards still behave (3.6, 3.7)
  - Optional, if a 1.23.X container is available: the same create/delete cycle on v1.x, confirming the full-list broadcast still drives the cache and the delta handlers never fire (3.1, 3.2)
  - If the post-delete read ever shows the removal racing, the documented fallback is a `pop(key, None)` after a successful `_call` in `delete_monitor` — idempotent with the handler. Report before applying it
  - _Requirements: 2.8, 1.4, 1.5, 2.4, 2.5, 3.1, 3.2, 3.6, 3.7_

## Notes

**Safety:** every regression test added here lives in the v2 unit files — no live
server, version and transport mocked. NEVER run bare `pytest tests/`: the
inherited integration tests wipe every monitor, notification, proxy, tag, status
page, docker host, maintenance and API key on the target instance during setup.
Use only the explicit file list given in the Overview.

### Task Dependency Graph

```
Evidence and baseline (all pre-fix):
        1 (write guard tests 14/15) ─> 2 (record the red failure) ─┐
        3 (preservation baseline, green pre-fix) ──────────────────┤
                                                                   └─> 4 (fix)

The fix:
        4.1 (Event members) ─> 4.2 (delta handlers) ─> 4.3 (_refresh + guards)
            ─> 4.4 (wait_for_event comment)
            ─> 4.5 (green: re-run task 1's tests) ─> 4.6 (preserve: re-run task 3's)

Remaining unit tests:
        {4.1, 4.2, 4.3} ─> 5 (handler + generated-input tests)
        4.3 ────────────> 6 (test_delete_id_coercion_v2.py unmodified)

Cleanup and bookkeeping:
        1 (new test file exists) ─> 8 (CHANGELOG + triage note)
        1 (new test file exists) ─> 9 (five-place CI list) ─> 10
        7 (scaffolding removal) — independent of the unit work, signed off by 11

Verification:
        {4, 5, 6, 9} ─> 10 (unit-verified completion point)
        {7, reachable disposable 2.x instance} ─> 11 (MANUAL; does NOT block 10)
```

- Tasks 1 → 2 → 4 and 3 → 4 are strictly sequential: the red failure must be
  recorded before the fix lands, and the preservation baseline must be observed
  on unfixed code to mean anything.
- Task 7 has no code dependency on the unit work and may be done at any point,
  but it stays unverified until task 11 runs the de-scaffolded script green.
- Task 9 must precede task 10 so the new test file actually runs in the
  checkpoint command.
- Task 11 is the only task that needs a live server. It may be skipped when no
  disposable 2.x instance is available; task 10 remains the completion point.
