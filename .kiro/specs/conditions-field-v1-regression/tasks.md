# Implementation Plan

## Overview

`_build_monitor_data` emits the Uptime Kuma **2.x-only** `conditions` field from
the unconditional common `data` dict (`api.py:968`), so every `add_monitor()`
call against a 1.x server sends a column the v1 schema does not have and the
insert is rejected with `SQLITE_ERROR: table monitor has no column named
conditions`. No caller opt-in is needed — the default path is enough, which makes
the most-used public method in the library unusable on v1. The regression shipped
in v2.1.0, v2.2.0 and v2.2.1.

The fix is four change groups, all in scope:

1. **Relocation** — move the `conditions` assignment into the existing
   `if self._parsed_version() >= parse_version("2.0"):` block at `api.py:1200`.
   This is the actual regression fix and is behaviour-neutral on v2.
2. **Explicit-opt-in rejection** — a private `_check_conditions_supported`
   helper raising `UptimeKumaException` from two call sites, so an explicitly
   requested `conditions` on a pre-2.0 server is never silently discarded.
3. **The seven adjacent v2-only fields** — gated in place, **silently, no raise**.
4. **Documentation and record-keeping.**

**The policy question is settled — do not reopen it.** The design's
`## Cross-Spec Policy Conflict` recommendation is ratified: the raise stays for
`conditions` (Change Group 2), silent omission for the seven adjacent fields
(Change Group 3), and a uniform library-wide "dropped v2-only field" signal is a
**separate follow-up spec**, noted in task 11 and designed nowhere in this spec.

Sequencing note: tasks 1-2 and task 3 exist as separate steps on purpose.
Requirement 2.9 demands the regression test be *demonstrated* to fail against the
unfixed code before the fix lands, and the design names the specific test that
must be red: `test_conditions_omitted_on_v1` in the new `TestConditionsV1Gate`
class. Writing that test and recording its verbatim pre-fix failure are two
distinct deliverables, and neither may be folded into the implementation task.
This follows the precedent set by `monitor-list-cache-staleness`.

**No CI-list update task is needed.** All new unit tests go into the **existing**
`tests/test_monitor_params_v2.py`, which is already named in all five CI-list
enumerations. The five-place update was a cost of the previous spec creating a
*new* test file; it does not apply here. Do not add a task for it. The new live
script in task 10 is `live_test_`-prefixed, so pytest never collects it and CI is
likewise unaffected — but the steering prose that enumerates the live scripts
does need updating, which task 10 covers.

Test command, used everywhere below (**never bare `pytest tests/`**, requirement
2.11 — the inherited integration tests wipe every monitor, notification, proxy,
tag, status page, docker host, maintenance and API key on the target instance
during setup):

```
pytest tests/test_monitor_types_v2.py tests/test_monitor_params_v2.py tests/test_status_page_v2.py tests/test_notification_v2.py tests/test_logger.py tests/test_monitor_builder.py tests/test_status_page_incidents.py tests/test_delete_id_coercion_v2.py tests/test_monitor_cache_v2.py -v
```

Environment note for whoever executes this: pytest is not installed on the bare
`python` on this machine. Use `.venv\Scripts\python.exe -m pytest ...` for every
command in this plan.

## Tasks

### Pre-fix evidence and preservation baseline

- [x] 1. Write the implicit bug-condition exploration tests
  - **Property 1: Bug Condition** - Implicit conditions omitted on pre-2.0 servers
  - **CRITICAL**: these tests MUST FAIL on unfixed code — the failure is the evidence requirement 2.9 asks for
  - **DO NOT** fix the tests or the code when they fail in task 3
  - **GOAL**: surface counterexamples proving `conditions` reaches a v1 payload with no caller opt-in whatsoever
  - Add a **new** `TestConditionsV1Gate(unittest.TestCase)` class at the end of `tests/test_monitor_params_v2.py`. Do not edit any existing class in that file
  - Reuse the file's established idiom: `setUp` builds a `MagicMock(spec=UptimeKumaApi)` with `api.version = "2.4.0"`, binds the real `_parsed_version` and `_build_monitor_data` via `UptimeKumaApi.<name>.__get__(api)`; a `_build_v1()` helper does the same with `api.version = "1.23.2"` (see `TestMonitorParamsV2.setUp` / `_build_v1`, lines 20-33)
  - `test_conditions_omitted_on_v1` — design exploratory case 1, **this is the named requirement 2.9 test**: `self._build_v1()(type=MonitorType.HTTP, name="t", url="http://x")`, assert `"conditions" not in result`. It needs no policy decision to be valid, which is why it is the designated evidence
  - `test_conditions_omitted_on_v1_all_types` — design exploratory case 2: the same assertion looped over HTTP, PING, PORT, DNS, KEYWORD and PUSH. This is the direct evidence for "unconditional, no opt-in needed"
  - `test_conditions_empty_list_omitted_on_v1` — design exploratory case 5: `conditions=[]` on v1 raises nothing **and** the key is absent. An explicit empty list is deliberately outside the bug condition, so this is the boundary case that pins the guard's truthiness test rather than an `is not None` test
  - **These tests encode the expected behaviour** — they are the same tests re-run in task 5.4 to validate the fix. Do not write new ones there
  - Run nothing yet; task 3 runs and records
  - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.9_

- [x] 2. Write the explicit-rejection exploration tests
  - **Property 2: Bug Condition** - Explicit conditions rejected on pre-2.0 servers
  - **CRITICAL**: these tests MUST also FAIL on unfixed code (no exception is raised today; the field is silently forwarded to the server)
  - Add to the same new `TestConditionsV1Gate` class
  - `test_explicit_conditions_raises_on_v1` — design exploratory case 3: `self._build_v1()(type=MonitorType.HTTP, name="t", url="http://x", conditions=[{...}])` raises `UptimeKumaException`. Assert the message names **all three** required elements: the field name `conditions`, the required version `2.0`, and the observed version string (`1.23.2`) — requirement 2.3 asks for all three, so a message assertion checking only the field name is insufficient
  - `test_edit_monitor_explicit_conditions_raises_on_v1` — design exploratory case 4: `edit_monitor(7, conditions=[{...}])` on a v1 mock raises `UptimeKumaException`, **and no server call was made** — mock `get_monitor` and `_call` on the instance and assert neither was invoked. That second assertion is what proves the guard sits ahead of `get_monitor(id_)`, which is requirement 2.3's "before any server call is made"
  - `test_builder_conditions_raises_on_v1` — the `MonitorBuilder` route: `MonitorBuilder().type(MonitorType.HTTP).name("t").url("http://x").conditions([{...}]).build()` splatted into the v1-bound builder raises the same exception. The builder is version-blind by design, so this proves the enforcement boundary is `add_monitor`/`edit_monitor` and not the builder (requirement 2.4)
  - **These tests encode the expected behaviour** — re-run unchanged in task 5.5
  - _Requirements: 1.3, 1.4, 1.5, 2.3, 2.4, 2.5_

- [x] 3. Run the exploration tests against the unfixed code and record the failure output
  - **Property 1: Bug Condition** - Implicit conditions omitted on pre-2.0 servers
  - Run exactly: `.venv\Scripts\python.exe -m pytest tests/test_monitor_params_v2.py -v -k TestConditionsV1Gate`
  - **EXPECTED OUTCOME**: every test written in tasks 1 and 2 FAILS. The task-1 tests fail on `"conditions" not in result` with the key present as `[]`; the task-2 tests fail because **no exception is raised at all**
  - **Verify the failure reason, not just the failure.** A task-1 failure must be an `AssertionError` showing `conditions: []` in the payload, not an `AttributeError` or a `TypeError` from harness drift. A task-2 failure must be "`UptimeKumaException` not raised", not an error from a mis-bound mock. Any other failure mode means task 1 or 2 needs correcting, not the code
  - Record the verbatim pytest output — test ids, assertion messages, and the offending payload dict — in the task notes and the PR description. **This is the requirement 2.9 evidence artifact and the fix must not land without it**
  - Do NOT implement anything in this task
  - Mark complete when the tests have been run, have failed for the right reasons, and the output is recorded
  - _Requirements: 2.9_

- [x] 4. Write the preservation tests and verify they pass on the unfixed code
  - **Property 3: Preservation** - v2 payloads byte-identical
  - Also covers **Property 4: Preservation** (non-`conditions` behaviour unchanged on both majors) and **Property 5: Preservation** (type validation still precedes version handling)
  - **IMPORTANT**: observation-first — run each case against the UNFIXED code, observe the actual result, then encode that observed result as the assertion. The v2 baseline is directly observable today, so these expectations are recorded from real behaviour, not guessed
  - Add to `TestConditionsV1Gate` (or a sibling `TestConditionsPreservation` class in the same file); do not edit existing classes
  - v2 default present — `"conditions" == []` on the `2.4.0` mock when the argument is absent (design preservation case 1, requirement 3.1)
  - v2 explicit passthrough **with identity** — pass a list of condition dicts and assert `result["conditions"] is passed_list` using `assertIs`. The identity assertion is the point: it pins the no-reallocation rule that backlog requirement 14.5 states only in prose, so a future switch to `conditions if conditions else list()` fails a test instead of passing review (design case 2, requirement 3.2)
  - v2 explicit empty list identity — `conditions=[]` on v2 yields the caller's own empty list object, not a fresh one (design case 3)
  - **`TypeError` ordering on both majors** — `conditions="not a list"` and `conditions={}` against both the `2.4.0` and the `1.23.2` mocks, asserting `TypeError` with the exact existing message `"conditions must be a list or None"`. On v1 this is the ordering proof for Property 5: `TypeError`, **not** `UptimeKumaException`. This is the one test that catches the new guard being placed above the `isinstance` check by mistake (design case 4, requirement 3.3)
  - Existing gates unmoved — `parent` at 1.22, `timeout` and `invertKeyword` at 1.23, `ipFamily` and `cacheBust` at 2.0 still appear at the same version boundaries (design case 5, requirement 3.4)
  - Non-`conditions` v1 payload identical — build the same monitor on v1 and compare the whole dict with `conditions` excluded against the observed pre-fix payload (design case 6, requirement 3.5)
  - `edit_monitor` merge path untouched — `edit_monitor(id_, interval=20)` on both majors with `get_monitor` and `_call` mocked: the merged payload and the `editMonitor` event are exactly as before and the new guard does not interfere (design case 7, requirement 3.6)
  - `MonitorBuilder` unchanged — `conditions()` still returns `self`, `build()` still emits only explicitly-set fields including `conditions` when set, and `build()` output is identical regardless of server version because the builder holds no connection (design case 8, requirement 3.7)
  - Run exactly: `.venv\Scripts\python.exe -m pytest tests/test_monitor_params_v2.py -v`
  - **EXPECTED OUTCOME**: every test in this task PASSES on the unfixed code (the task 1-2 tests still fail — that is correct). These passes are the baseline to preserve
  - Mark complete when written, run, and passing pre-fix
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

### The fix

- [x] 5. Fix the unconditional `conditions` emission on pre-2.0 servers

  - [x] 5.1 Relocate the `conditions` assignment into the existing `>= 2.0` block (change group 1)
    - In `uptime_kuma_api/api.py`, **delete** line 968 from the common `data` dict literal: `"conditions": conditions if conditions is not None else [],`. The literal then ends at `"httpBodyEncoding": httpBodyEncoding,`; nothing else in it moves
    - **Add** it as the first statement inside the existing `if self._parsed_version() >= parse_version("2.0"):` block at `api.py:1200`, under the `# v2-only parameters (gated behind version check)` comment and before the `# Network monitors: ipFamily` sub-block: `data["conditions"] = conditions if conditions is not None else []`
    - **Copy the expression verbatim** — `conditions if conditions is not None else []`, never `conditions if conditions else list()`. The `is not None` form returns the caller's own object for both a non-empty list and an explicit `[]`; the PR #86 form allocates a fresh list and conflates `None` with `[]`. Declining that pattern is a standing instruction (backlog requirement 14.5) and task 4's `assertIs` pins it
    - **Do not create a second `>= 2.0` block.** Reuse the existing one so requirement 3.4's "whole existing `>= 2.0` block" stays a single unit and the gate-count assumptions in the test apparatus stay true
    - Use `self._parsed_version()`, never the raw `parse_version(self.version)` form — the raw form was replaced project-wide by the `release-2-3-0-fixes` spec
    - Note for the reviewer, already settled in the design: `conditions` moves from index 11 of the emitted dict to the front of the v2 block, i.e. later in insertion order. Not behaviourally significant — the payload is serialised to JSON and consumed as an object, and no test compares `list(data.keys())` or a `repr`
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.4_

  - [x] 5.2 Add the private guard and its two call sites (change group 2)
    - Add `_check_conditions_supported(self, conditions) -> None` on `UptimeKumaApi`, immediately after `_parsed_version()` (~line 775) so the version-gating machinery stays together. Body: `if conditions and self._parsed_version() < parse_version("2.0"):` raise `UptimeKumaException` naming the field, the required version (2.0 or newer) and `self.version`
    - Private (leading underscore), so **no new public API surface** — requirement 2.7 is satisfied. A new exception *message* is not surface. Do not export it, do not add it to `docs/api.rst`
    - The docstring must record *why* this one field raises where the seven adjacent fields do not: `conditions` defines the monitor's up/down semantics, so a silently discarded value produces a monitor that reports success against criteria the caller never set. The other v2-only fields change *how* the check runs and fail observably
    - **Call site A — `_build_monitor_data`**: insert `self._check_conditions_supported(conditions)` in the validation preamble **immediately after** the existing `TypeError` check at `api.py:945-946`. This placement is load-bearing for Property 5 — the `TypeError` is the earliest validation in the method and the guard sits directly behind it, so a non-list value on a v1 server raises `TypeError` and never reaches the version check. It also means the guard can only ever see `None` or a genuine list, so its truthiness test is unambiguous
    - **Call site B — `edit_monitor`** (`api.py:1773`): `self._check_conditions_supported(kwargs.get("conditions"))` as the **first** statement, before `data = self.get_monitor(id_)`. Check `kwargs`, not the merged `data`, so the guard can only ever react to what the caller asked for and never to something a server echoed back. Placing it before `get_monitor(id_)` is what satisfies "before any server call is made"; the guard itself makes no call, since `_parsed_version()` reads `self.version`, which reads cached `Event.INFO` data
    - **Exactly two call sites, not three.** `add_monitor` needs no change of its own — it calls `_build_monitor_data(**kwargs)` on its first line, so site A covers both `add_monitor(conditions=...)` and `add_monitor(**builder.build())`; site B covers both `edit_monitor` routes
    - **Zero changes to `MonitorBuilder`.** It is a connection-less dict wrapper with no `self.version` and no `_parsed_version()`, so it cannot know the server major; giving it one would mean a public API change (forbidden by 2.7). Enforcing at the `add_monitor`/`edit_monitor` boundary covers requirement 2.4 and is what preserves 3.7
    - **Not in `_check_arguments_monitor`.** It is a module-level function (`api.py:253`) taking only `kwargs`, with no `self` and therefore no version access. Converting it or threading the version through it would touch the shared validation path for every monitor field to gate one — rejected as disproportionate
    - Accepted asymmetry, recorded as a judgment call: a *non-list truthy* `conditions` passed to `edit_monitor` on v1 now raises `UptimeKumaException` (version) where `add_monitor` raises `TypeError` (type). Not a preservation break — `edit_monitor` does not raise `TypeError` for that input today either, it forwards the value and lets the server reject it. Adding an `isinstance` check to `edit_monitor` would be new validation on a path requirement 3.6 says to leave alone
    - _Bug_Condition: `isBugCondition(input)` explicit sub-case from the design — a truthy `conditions` value reaching `add_monitor` or `edit_monitor` against a server older than 2.0_
    - _Expected_Behavior: design Correctness Property 2 — `UptimeKumaException` naming the field, the required version and the observed version, raised before any server call_
    - _Preservation: design Preservation Requirements — `MonitorBuilder` untouched, `edit_monitor`'s merge path untouched, `TypeError` still first_
    - _Requirements: 2.3, 2.4, 2.5, 2.7_

  - [x] 5.3 Gate the seven adjacent v2-only fields in place, silently (change group 3)
    - **No raise for any of these seven** — silent omission, per the ratified policy. They are already explicit-opt-in-only, requirement 1.6 records that whether each actually fails on v1 is *unverified*, and raising would convert a possibly-working path into a guaranteed hard error. Silent omission also matches backlog requirement 13.3 and the block they conceptually join, so it adds no new inconsistency
    - They sit inside type-specific blocks, so add the version condition **in place** rather than moving them into the `>= 2.0` block — moving would mean duplicating their type guards
    - `jsonPathOperator` (`api.py:1133-1134`), inside `if type == MonitorType.JSON_QUERY`: `if jsonPathOperator is not None and self._parsed_version() >= parse_version("2.0"):`
    - `snmp_v3_username` (`api.py:1169-1170`), inside `if type == MonitorType.SNMP`: same shape. Expect no behavioural change in practice — the `SNMP` monitor type is itself v2-only, so a v1 server rejects the type before the field matters. Gated for uniformity
    - `ping_count`, `ping_numeric`, `ping_per_request_timeout` (`api.py:1183-1191`), inside `if type == MonitorType.PING`: wrap the three `is not None` checks in **one** nested version gate rather than repeating the condition three times
    - `mqttWebsocketPath`, `mqttCheckType` (`api.py:1193-1197`), inside `if type == MonitorType.MQTT`: same nested-gate shape as PING
    - **Leave the input validation unconditional.** The `ValueError` checks for `mqttCheckType` and `mqttWebsocketPath` length in the preamble (`api.py:951-956`) are argument validation, not payload emission. They must keep firing on both majors — a bad value is a bad value regardless of server version, and gating them would be a silent relaxation
    - _Bug_Condition: `isBugCondition` one level up — an explicitly supplied v2-only field emitted outside the `>= 2.0` gate against a pre-2.0 server (requirement 1.6)_
    - _Expected_Behavior: design Correctness Property 6 — omitted on v1 without raising, present on v2 exactly as before_
    - _Preservation: design Preservation Requirements — the `ValueError` argument validation still fires on both majors_
    - _Requirements: 1.6, 2.6, 3.5_

  - [x] 5.4 Verify the implicit bug-condition tests now pass
    - **Property 1: Expected Behavior** - Implicit conditions omitted on pre-2.0 servers
    - **IMPORTANT**: re-run the SAME tests from task 1 — do NOT write new tests and do NOT edit those tests
    - Run exactly: `.venv\Scripts\python.exe -m pytest tests/test_monitor_params_v2.py -v -k TestConditionsV1Gate`
    - **EXPECTED OUTCOME**: `test_conditions_omitted_on_v1`, `test_conditions_omitted_on_v1_all_types` and `test_conditions_empty_list_omitted_on_v1` now PASS, confirming the v1 payload carries no unsupported column
    - _Requirements: 2.1, 2.2_

  - [x] 5.5 Verify the explicit-rejection tests now pass
    - **Property 2: Expected Behavior** - Explicit conditions rejected on pre-2.0 servers
    - **IMPORTANT**: re-run the SAME tests from task 2 — do NOT write new tests and do NOT relax the message assertions
    - **EXPECTED OUTCOME**: all three now PASS. Confirm the message genuinely contains the field name, `2.0` and the observed version, and that the `edit_monitor` case still asserts neither `get_monitor` nor `_call` was invoked
    - _Requirements: 2.3, 2.4, 2.5_

  - [x] 5.6 Verify the preservation tests still pass
    - **Property 3: Preservation** - v2 payloads byte-identical
    - **IMPORTANT**: re-run the SAME tests from task 4 — do NOT write new tests and do NOT relax any assertion
    - **EXPECTED OUTCOME**: every task-4 test still PASSES — v2 default `[]` present, explicit list passed through as the caller's own object, `TypeError` still first on both majors, existing gates at unchanged boundaries, non-`conditions` v1 payload identical, `edit_monitor` merge path unchanged, `MonitorBuilder` unchanged
    - If the `TypeError`-ordering test is the one that fails, the guard was placed above the `isinstance` check — fix the placement in 5.2, not the test
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

### Remaining unit tests

- [x] 6. Add the adjacent-field tests and the seeded generated-input tests

  - [x] 6.1 Add the seven-adjacent-field tests
    - **Property 6: Preservation** - Adjacent v2-only fields gated without new errors
    - For each of `jsonPathOperator`, `snmp_v3_username`, `ping_count`, `ping_numeric`, `ping_per_request_timeout`, `mqttWebsocketPath` and `mqttCheckType`: supplied explicitly on the `1.23.2` mock, the field is **absent** from the payload and **nothing is raised**; on the `2.4.0` mock it is present exactly as today
    - Assert the absence of a raise **explicitly**, so a future change that adds one fails a test rather than passing unnoticed. That negative assertion is the executable form of the ratified policy
    - Confirm the `mqttCheckType` / `mqttWebsocketPath` `ValueError` argument validation still fires on **both** majors for an invalid value
    - _Requirements: 2.6, 3.5_

  - [x] 6.2 Add the seeded generated-input tests
    - **Property 1: Bug Condition** - Implicit conditions omitted on pre-2.0 servers
    - Follow the seeded-generator idiom already in this file (`generate_valid_pep440_versions`, a fixed `random.Random` seed, a bounded case count). **Hypothesis is deliberately not a project dependency**; a fixed seed keeps CI reproducible
    - Version boundary — over generated valid PEP440 version strings, assert `"conditions" in payload` **iff** `parse_version(raw) >= parse_version("2.0")`. This is the version-boundary form of Properties 1 and 3 and covers pre-releases, post-releases, dev-releases and local versions around the boundary, not just plain triples
    - Monitor type × parameter combinations on v1 — assert `conditions` is never present, and that no `UptimeKumaException` is raised unless `conditions` was explicitly supplied truthy
    - Condition-list shapes on v2 — assert the emitted value is the same object that was passed in (the identity / no-reallocation property)
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2_

- [x] 7. Verify the existing gate apparatus is undisturbed
  - **Property 4: Preservation** - Non-conditions behaviour unchanged on both majors
  - **Verify, do not assume, and do not edit these.** The design reasons they are safe because both probes call `_build_monitor_data` **without** a `conditions` argument, so the new guard never fires for them, and both detect the `2.0` gate through `ipFamily` / `cacheBust` presence, which change group 1 does not touch. Confirm that by reading and running, not by trusting the design
  - Confirm unchanged and unedited in `tests/test_monitor_params_v2.py`: `GATE_CONSTANTS = ["1.22", "1.23", "1.23.1", "2.0"]` (~line 690), `_monitor_gates` (~line 904), `_assert_gated_path_runs`, and the `TestValidVersionGatePreservation` and `TestUnparseableVersionBugCondition` classes
  - `GATE_CONSTANTS` needs **no new entry** — `2.0` is already there and no new gate constant is introduced
  - Run exactly: `.venv\Scripts\python.exe -m pytest tests/test_monitor_params_v2.py -v`
  - **EXPECTED OUTCOME**: every pre-existing test in the file passes with **zero edits to any pre-existing class**. If one of those two classes needs a change, stop and report it — it means the fix touched a gate it should not have
  - Also confirm the two other cache-related classes in the file (`TestMonitorTagCacheBugCondition`, `TestMonitorTagCachePreservation`) are untouched and green
  - _Requirements: 3.4, 3.9_

- [x] 8. Add the missing version skip to the inherited DNS integration test
  - **Property 4: Preservation** - Non-conditions behaviour unchanged on both majors
  - `tests/test_monitor.py::test_monitor_type_dns` (~line 186) passes an explicit `conditions` list but, unlike its siblings `test_monitor_conditions` (~line 381) and `test_monitor_dns_conditions` (~line 395), carries **no** `< 2.0` skip guard
  - Add the same guard those two use: `if parse_version(self.api.version) < parse_version("2.0"): self.skipTest("Unsupported in this Uptime Kuma version")`
  - This is a correctness fix to the test, not an accommodation of the new behaviour: the test is red on v1 **today** with the SQLITE error, and would be red under either policy choice — under the raise with the new `UptimeKumaException`, under silent omission with an `ABSENT` round-trip mismatch
  - **Inherited integration suite, not CI.** No CI-list implication. Do not run this file — see the safety note below
  - _Requirements: 1.3, 2.3, 3.9_

### New live script and bookkeeping

- [x] 9. Write the v1 live verification script
  - New file `tests/live_test_conditions_v1.py`, following the existing `live_test_*.py` conventions: env-var driven, `record()`-style PASS/FAIL accounting, non-zero exit on any failure
  - **ASCII-only output.** `PASS` / `FAIL` / `->` only — no check marks, no box-drawing. Non-ASCII has crashed scripts mid-run on the cp1252 console
  - Read the target from env vars for a **disposable v1 container** (e.g. `UPTIME_KUMA_V1_URL`, `UPTIME_KUMA_V1_USERNAME`, `UPTIME_KUMA_V1_PASSWORD`), referenced by key name only — never print a secret value. Refuse to run with a clear message if the URL is unset, rather than defaulting to anything
  - A fresh container has no admin user, so the script bootstraps it: `need_setup()` -> `setup(username, password)` -> `login(...)`
  - **Assert `api.version` starts with `1.23` before doing anything else** and abort otherwise. The whole run is meaningless if it is accidentally pointed at a v2 instance, and this is also the guard against pointing it at a real instance by mistake
  - The steps, per the design's Live Verification Plan: `add_monitor(type=HTTP, name="v1-conditions-gate", url="http://127.0.0.1")` with **no** `conditions` argument and **no** `pop("conditions")` workaround, expecting `{'msg': 'Added Successfully.', 'monitorID': n}`; a `get_monitor(n)` round-trip comparing sent vs returned fields, because "the server didn't reject it" is not verification; the same add for a second type (PING) to show the fix is not HTTP-specific; `add_monitor(..., conditions=[{...}])` expecting `UptimeKumaException` **and** confirming no monitor was created; `edit_monitor(n, interval=120)` succeeding; `edit_monitor(n, conditions=[{...}])` expecting the same exception
  - Prominent module-docstring warning: disposable instances only. The script creates monitors and must never be pointed at anything that matters
  - The `live_test_` prefix keeps pytest from collecting it, so **CI is unaffected and no CI-list enumeration changes** — confirm that by running the nine-file command in task 12 and seeing the collected count unchanged for the other files
  - _Requirements: 2.8, 2.11_

- [x] 10. Update the live-script enumerations
  - `.kiro/steering/structure.md` (~lines 32-38) carries a prose enumeration of the live scripts — `live_test_backup.py`, `live_test_create.py`, `live_test_cleanup.py`, `live_test_ssl_verify.py`, `live_test_delete_id.py`. Add `live_test_conditions_v1.py` with its distinguishing constraint: unlike the others it targets a **disposable v1.23.x container**, not the 2.x instance, and reads its own env vars rather than the `tests/.env` 2.x keys
  - **Verify by grep, not by trusting any documented list.** Run a repo-wide `grep -rn "live_test_"` and update every enumeration it finds. As of writing, the hits outside spec docs are `.kiro/steering/structure.md` (the prose enumeration) and `.kiro/steering/testing.md` (~lines 43-46, the 2.x live-cycle command block). The precedent for this caution is real: the previous spec found a sixth, already-stale CI-suite list in `README.md` that the documented five-place enumeration had missed
  - For `.kiro/steering/testing.md`, decide deliberately rather than by reflex: that block is the **2.x** backup -> create -> dry-run -> cleanup cycle, and the new script is a v1-only, differently-configured one-off. Adding it to that sequence would be wrong; mention it separately if at all
  - _Requirements: 2.8_

- [x] 11. Write the changelog entry and record the narrowed assertions
  - `CHANGELOG.md` — the top section is the **unreleased** `### Release 2.3.1` (`__version__.py` still reads `2.3.0`), so this entry joins that section's `#### Bugfixes` rather than opening a new one. Its intro paragraph currently reads "One defect, found during 2.3.0 live verification..." and must be updated to account for two
  - The entry must frame this as a fix to a **released regression present in v2.1.0, v2.2.0 and v2.2.1** (introduced by `70138bf`, confirmed via `git tag --contains`), not an unreleased defect — requirement 2.10. State that `add_monitor()` was totally unusable on every 1.x server with no caller opt-in required, name the SQLITE error, and record that no public API surface was added
  - Document the raise-vs-omit split explicitly and why: `conditions` raises because it defines the monitor's up/down semantics and a silent drop yields a monitor that reports success against criteria the caller never set; the seven adjacent v2-only fields are omitted silently because they are opt-in-only, change *how* a check runs rather than its verdict, and match the existing block's behaviour. A caller cannot derive raise-vs-drop from first principles, so it has to be written down here
  - **Record the narrowing of two earlier specs' assertions as a first-class deliverable, not a footnote.** If these are not annotated, the next contributor reads them as current and reverts this fix:
    1. `.kiro/specs/uptime-kuma-v2-support/design.md` — *Property 1: Default conditions is empty list* (~line 133, plus the `# <-- NEW: always present, defaults to empty list` comment at ~line 123). Annotate in place that it is **superseded by `conditions-field-v1-regression`** and now holds only for server versions >= 2.0. It was correct only for v2
    2. `.kiro/specs/uptime-kuma-v2-support-backlog/requirements.md` — requirement 13.3 (~line 178, "omit those parameters ... without raising an error or logging a warning"). Annotate that it remains the rule for the seven adjacent fields but is **narrowed for `conditions`**, which raises, with a pointer to this spec's `## Cross-Spec Policy Conflict` for the severity argument
  - Record two follow-ups as notes only, **not** designed or implemented here:
    1. A uniform library-wide "dropped v2-only field" signal, which would let the `conditions` raise be retired and restore one predictable rule. This is what makes the inconsistency explicitly temporary and tracked rather than permanent and accidental
    2. Monitor **types** `RABBITMQ`, `SNMP`, `SMTP` and `SYSTEM_SERVICE` are themselves v2-only and ungated — the same defect class one level up, but out of this spec's requirements and it fails loudly rather than silently
  - `UPSTREAM_TRIAGE.md` — a short note that this was found during the `monitor-list-cache-staleness` v1 verification run and that the `pop("conditions")` workaround used there is no longer needed. A few lines only
  - **Do not touch `uptime_kuma_api/__version__.py`.** Version bumping is a release-time decision, out of scope
  - No `docs/api.rst` change and no `__init__.py` export change — nothing public is added
  - _Requirements: 2.7, 2.10_

### Verification

- [x] 12. Checkpoint - unit suite green
  - Run exactly (**never bare `pytest tests/`**):
    ```
    .venv\Scripts\python.exe -m pytest tests/test_monitor_types_v2.py tests/test_monitor_params_v2.py tests/test_status_page_v2.py tests/test_notification_v2.py tests/test_logger.py tests/test_monitor_builder.py tests/test_status_page_incidents.py tests/test_delete_id_coercion_v2.py tests/test_monitor_cache_v2.py -v
    ```
  - Confirm every new test in `tests/test_monitor_params_v2.py` passes, including the seeded generated-input tests
  - Confirm no pre-existing test in any of the nine files regressed, and that no pre-existing class in `tests/test_monitor_params_v2.py` was edited (task 7)
  - **Revert-and-recheck before the PR**: temporarily undo change group 1 and confirm `test_conditions_omitted_on_v1` goes red again, then restore. A test that has only ever passed proves nothing
  - Confirm no new public method, parameter, class or export was added; `docs/api.rst` and `__init__.py` are unchanged; `__version__.py` is unchanged
  - Confirm every new gate uses `self._parsed_version()` and not the raw `parse_version(self.version)` form
  - **This checkpoint proves the change is internally correct, but it is NOT the completion point for this spec.** Requirement 2.8 makes a successful live `add_monitor()` against a real 1.23.2 server an explicit acceptance criterion, so task 13's v1 half is an obligation, not optional confirmation — unlike the previous spec, where the unit checkpoint stood alone. If the v1 container cannot be run, say so plainly in the PR and mark the fix **unverified against 2.8**; do not treat this checkpoint as done in its place. Ask the user if any question arises
  - _Requirements: 2.7, 2.9, 2.11, 3.9_

- [x] 13. MANUAL - live verification against both server majors
  - **Not CI. Not automated. Disposable instances only.** The v1 half is the requirement 2.8 acceptance criterion (see task 12) — the v2 half is confirmation that nothing regressed
  - **v1 — disposable 1.23.2 container.** Start it over `ssh <user>@<docker-host>` on host port **3023**; 3001 and 3022 are already taken by existing Kuma instances and Nginx Proxy Manager holds 80, 81 and 443:
    ```
    ssh <user>@<docker-host> "docker run -d --name kuma-v1-conditions -p 3023:3001 louislam/uptime-kuma:1.23.2"
    ```
    Run `tests/live_test_conditions_v1.py` against `http://<docker-host>:3023`. The library bootstraps the fresh container itself via `need_setup()` / `setup()` / `login()`
  - **The acceptance criterion**: `add_monitor()` succeeds through the real public method with **no** `pop("conditions")` workaround — the workaround that made the original discovery run complete — returning `{'msg': 'Added Successfully.', 'monitorID': n}`, with the `get_monitor(n)` round-trip confirming what was created matches what was sent. Record the actual output
  - Also confirm on the live v1 server: the second monitor type (PING) creates, `edit_monitor(n, interval=120)` succeeds (3.6 on a real v1 server), and both explicit-`conditions` calls raise `UptimeKumaException` naming the field and version with no monitor created
  - **Teardown**: `ssh <user>@<docker-host> "docker rm -f kuma-v1-conditions"`. The container runs without a volume, so removing it destroys all its state and nothing is shared with the other instances on that host. Do not leave it running
  - **v2 — the existing disposable 2.5.0 instance** via the `tests/.env` keys `UPTIME_KUMA_URL`, `UPTIME_KUMA_USERNAME` and `UPTIME_KUMA_PASSWORD`, referenced by name only; values stay in the gitignored file and are never printed:
    1. `.venv\Scripts\python.exe tests/live_test_backup.py` — config snapshot **first**, always
    2. `.venv\Scripts\python.exe tests/live_test_create.py` — already exercises `MonitorBuilder(...).conditions([...])` end to end, so it covers the v2 builder path and the sent-vs-returned round-trip comparison (`ABSENT` / `MISMATCH`) for `conditions` with no modification
    3. `.venv\Scripts\python.exe tests/live_test_cleanup.py --dry-run`, inspect the output, then the real `.venv\Scripts\python.exe tests/live_test_cleanup.py`
  - **Do not add the v1 container to CI.** CI stays the nine-file unit suite; the container run is a documented manual step recorded here and in the PR description
  - _Requirements: 2.8, 2.1, 2.3, 3.1, 3.2, 3.6_

## Notes

**Safety:** every automated test added here lives in the existing
`tests/test_monitor_params_v2.py`, with the version and transport mocked and no
live server. NEVER run bare `pytest tests/` (requirement 2.11): the inherited
integration tests wipe every monitor, notification, proxy, tag, status page,
docker host, maintenance and API key on the target instance during setup. Use
only the explicit nine-file list in the Overview. Task 8 edits
`tests/test_monitor.py` but must not run it.

**Secrets:** `tests/.env` credentials are referred to by key name only. Never
print a secret value, and never commit `tests/.env`, `tests/.backups/` or
`tests/.live_test_ids.json`.

**Scope:** no new public API surface (requirement 2.7). A private helper and a new
exception message are fine. The uniform "dropped v2-only field" signal and the
ungated v2-only monitor *types* are follow-up notes in task 11, not work items
here.

### Task Dependency Graph

```
Evidence and baseline (all pre-fix):
        1 (implicit bug-condition tests) ─┐
        2 (explicit-rejection tests) ─────┴─> 3 (record the red failure) ─┐
        4 (preservation baseline, green pre-fix) ─────────────────────────┤
                                                                         └─> 5 (fix)

The fix:
        5.1 (relocate conditions) ─> 5.4 (green: re-run task 1's tests)
        5.2 (guard + 2 call sites) ─> 5.5 (green: re-run task 2's tests)
        5.3 (seven adjacent fields)
        {5.1, 5.2, 5.3} ───────────> 5.6 (preserve: re-run task 4's tests)

Remaining unit tests:
        5.3 ───────────> 6.1 (adjacent-field tests, no-raise assertions)
        {5.1, 5.2} ────> 6.2 (seeded generated-input tests)
        {5.1, 5.2, 5.3} ─> 7 (gate apparatus undisturbed, zero edits)
        independent ─────> 8 (test_monitor.py DNS skip; red on v1 today regardless)

New live script and bookkeeping:
        {5.1, 5.2} ─> 9 (live_test_conditions_v1.py) ─> 10 (steering enumerations)
        {5.1, 5.2, 5.3} ─> 11 (CHANGELOG + narrowed assertions + follow-up notes)

Verification:
        {5, 6, 7, 8, 11} ─> 12 (unit-verified, NOT the completion point)
        {9, 12, disposable 1.23.2 container} ─> 13 (MANUAL; v1 half is required by 2.8)
```

- Tasks 1-2 → 3 → 5 and 4 → 5 are strictly sequential: the red failure must be
  recorded before the fix lands, and the preservation baseline must be observed on
  unfixed code to mean anything.
- Task 8 has no dependency on the fix — that test is red on v1 today for its own
  reasons — and may be done at any point.
- Task 9 must precede task 10 (the file has to exist before it is enumerated) and
  precede task 13 (it is what task 13 runs).
- **Task 13 is not optional in the way the previous spec's live task was.**
  Requirement 2.8 names a successful live v1 `add_monitor()` as an acceptance
  criterion, so task 12 alone does not close this spec. If no disposable 1.23.2
  container is reachable, record the gap explicitly rather than absorbing it.
