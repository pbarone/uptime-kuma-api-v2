# Conditions Field v1 Regression Bugfix Design

## Overview

`_build_monitor_data` emits the Uptime Kuma **2.x-only** `conditions` field in
the unconditional common `data` dict, so every `add_monitor()` call against a
1.x server sends a column the v1 schema does not have and the insert is rejected
with `SQLITE_ERROR: table monitor has no column named conditions`. No v2-specific
input is needed to trigger it — the default path is enough, which makes the
most-used public method in the library totally unusable on v1.

The fix has two halves, and they are worth keeping distinct because they answer
different requirements and carry very different risk:

1. **Relocation** (the actual regression fix). Move the `conditions` assignment
   out of the common dict and into the `>= 2.0` block that already gates every
   other v2-only field in the same method. This restores v1 for the default path
   and is behaviour-neutral on v2.
2. **Explicit-opt-in rejection** (a policy addition). Raise
   `UptimeKumaException` when a caller explicitly asks for `conditions` against
   a pre-2.0 server, rather than silently discarding what they asked for.

Half 1 is uncontroversial: it is exactly the shape the codebase already uses,
and it is the half that satisfies the project's non-negotiable v1 principle.
Half 2 **directly contradicts an approved, already-implemented policy in an
earlier spec**. That conflict is resolved explicitly in
[Cross-Spec Policy Conflict](#cross-spec-policy-conflict) below, with a
recommendation the user needs to ratify before implementation starts. Everything
downstream of that section is written for the recommended resolution and flags
the single line that changes if the user decides otherwise.

Scope is deliberately narrow: a version gate on existing fields. No new public
method, no new public parameter, no signature change (requirement 2.7).

## Glossary

- **Bug_Condition (C)**: The set of inputs that trigger the defect —
  `isBugCondition` below.
- **Property (P)**: The desired behaviour of the fixed code on inputs where `C`
  holds.
- **Preservation**: For all inputs where `C` does NOT hold, the fixed code `F'`
  produces the same result as the original `F`. For this bug that means **v2
  behaviour must be byte-identical**.
- **F / F'**: The original (unfixed) / fixed function.
- **`_build_monitor_data`**: The private payload builder in
  `uptime_kuma_api/api.py` (signature starts ~line 778) that assembles the
  monitor dict for both `add_monitor` and, indirectly, nothing else — see
  `edit_monitor` below.
- **Common `data` dict**: The unconditional dict literal at `api.py:958-969`,
  built before any version gate runs. `conditions` is assigned at **`api.py:968`**.
- **The `>= 2.0` block**: `if self._parsed_version() >= parse_version("2.0"):` at
  **`api.py:1200`**, preceded by the comment
  `# v2-only parameters (gated behind version check)`. It already gates
  `ipFamily`, the HTTP set (`cacheBust`, `retryOnlyOnStatusCodeFailure`,
  `bearer_token`, `oauth_audience`, `domainExpiryNotification`, `saveResponse`,
  `saveErrorResponse`, `responseMaxLength`, `responsecheck`) and the
  low-priority set (`subtype`, `wsSubprotocol`,
  `wsIgnoreSecWebsocketAcceptHeader`, `remoteBrowsersToggle`,
  `remote_browser`, `screenshot_delay`, `gamedigToken`, `protocol`).
- **`_parsed_version()`**: The single version-gate choke point at `api.py:761`,
  introduced by the `release-2-3-0-fixes` spec. It returns
  `parse_version(self.version)`, or a `9999` sentinel for an unparseable
  (nightly/garbage) version so such a server is treated as newest. **All new
  gates use `self._parsed_version()`**; the raw `parse_version(self.version)`
  form is the old idiom and was replaced project-wide.
- **`version` property**: `api.py:757` — `self.info().get("version")`. `info()`
  reads cached event data (`_get_event_data(Event.INFO)`, `api.py:2870`), **not**
  the network, so a version-gated guard costs no server round-trip.
- **`MonitorBuilder`**: The fluent builder in `uptime_kuma_api/monitor_builder.py`.
  `conditions()` (line 72) writes `_data["conditions"]` directly; `build()`
  returns only explicitly-set fields. The builder holds a plain dict and has **no
  server connection and therefore no version knowledge**.
- **Adjacent v2-only fields**: The seven fields named in requirement 1.6 that are
  emitted outside the `>= 2.0` block but only on explicit opt-in —
  `jsonPathOperator` (`api.py:1133-1134`), `snmp_v3_username`
  (`api.py:1169-1170`), `ping_count` / `ping_numeric` /
  `ping_per_request_timeout` (`api.py:1183-1191`), `mqttWebsocketPath` /
  `mqttCheckType` (`api.py:1193-1197`).

## Bug Details

### Bug Condition

The bug manifests whenever a monitor payload destined for a pre-2.0 server
carries a `conditions` key. There are two distinct sub-cases, and they differ in
severity: the **implicit** case fires with no caller opt-in at all (every
`add_monitor` call), while the **explicit** case requires the caller to name the
field.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input = (path, serverVersion, conditionsArg)
         path IN {add_monitor, edit_monitor}          // MonitorBuilder feeds both
         serverVersion = the version string reported by the server
         conditionsArg = the caller-supplied conditions value, or ABSENT
  OUTPUT: boolean

  IF parsedVersion(serverVersion) >= 2.0 THEN
    RETURN false                                       // v2 is correct today
  END IF

  // implicit: no opt-in required, fires on every add_monitor call
  IF path = add_monitor AND conditionsArg = ABSENT THEN
    RETURN true                                        // payload still carries "conditions": []
  END IF

  // explicit: caller named the field (kwarg or MonitorBuilder.conditions())
  RETURN conditionsArg IS NOT ABSENT AND isTruthy(conditionsArg)
END FUNCTION
```

Note the asymmetry the predicate encodes: for `add_monitor` the ABSENT case is
buggy (the key is emitted anyway), whereas for `edit_monitor` the ABSENT case is
**not** buggy — that path merges `get_monitor(id_)` output, and a v1 server never
returns a `conditions` key, so nothing is sent.

An explicitly-passed **empty** list is deliberately outside the bug condition:
`conditions=[]` is indistinguishable in effect from the default, so it is treated
as "no conditions requested" and simply omitted on v1 rather than rejected. This
is why the guard tests truthiness rather than `is not None`.

### Examples

- `add_monitor(type=HTTP, name="x", url="http://x")` against 1.23.2 → payload
  contains `"conditions": []`, server raises
  `SQLITE_ERROR: table monitor has no column named conditions`, **no monitor
  created** (bug); expected: key absent, monitor created.
- `add_monitor(..., conditions=[{...}])` against 1.23.2 → same SQLITE failure,
  with nothing naming the version requirement (bug); expected:
  `UptimeKumaException` naming `conditions`, the required version and the
  observed version, raised before any server call.
- `add_monitor(**MonitorBuilder().type(HTTP).name("x").url(...).conditions([{...}]).build())`
  against 1.23.2 → identical to the previous case, because `build()` emits the
  same `conditions` kwarg (bug).
- `edit_monitor(7, conditions=[{...}])` against 1.23.2 → merged dict carries the
  key into `editMonitor`, server rejects the update (bug); expected: same
  `UptimeKumaException`.
- `edit_monitor(7, interval=20)` against 1.23.2 → merge + `editMonitor` succeed
  today (NOT a bug; preserved).
- `add_monitor(type=HTTP, name="x", url="http://x")` against 2.5.0 → payload
  contains `"conditions": []`, monitor created (NOT a bug; preserved).
- `add_monitor(..., conditions="nope")` on either major → `TypeError("conditions
  must be a list or None")` (NOT a bug; preserved, and must still fire *first*).

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviours:**

- v2 payloads are byte-identical: `"conditions": []` still present by default
  (3.1), an explicit list still passed through unvalidated (3.2).
- The explicit list must be passed through **without reallocation** — the
  emitted value is the caller's own list object. This is the executable form of
  the standing instruction not to adopt PR #86's
  `conditions if conditions else list()` pattern (`uptime-kuma-v2-support-backlog`
  requirement 14.5, `uptime-kuma-v2-support/backlog.md:112`: it "replaces an
  intentional `[]` with a new list"). The existing
  `conditions if conditions is not None else []` expression must move verbatim.
- `TypeError("conditions must be a list or None")` still fires for a non-list
  value, on both majors, **before** any version-dependent handling (3.3).
- Every existing version gate untouched: `parent` at 1.22 (`api.py:971`),
  `invertKeyword` at 1.23 (`api.py:980`), `timeout` at 1.23 (`api.py:1006`),
  `gamedigGivenPortOnly` at 1.23 (`api.py:1122`), and the whole `>= 2.0` block
  (3.4).
- Every non-`conditions` field in the v1 payload identical to today (3.5).
- `edit_monitor` without a `conditions` kwarg merges and calls exactly as today
  on both majors (3.6).
- `MonitorBuilder` setter signatures and `build()` semantics unchanged (3.7) —
  the builder needs **zero** code changes.
- `get_monitor` / `get_monitors` response shapes unchanged (3.8).

**Scope:**

Anything not carrying a `conditions` key toward a pre-2.0 server is unaffected:

- every call against a 2.x server, of any shape;
- every v1 call that does not mention `conditions` (after the relocation);
- reads (`get_monitor`, `get_monitors`), tags, notifications, status pages,
  maintenance, settings;
- the `MonitorBuilder` class itself.

A previously-asserted property is **deliberately narrowed**: the originating
`uptime-kuma-v2-support` spec's *Property 1: Default conditions is empty list*
asserted unconditional presence. That was only ever correct for v2 and is
superseded here, restricted to `>= 2.0`. Verified: the v2 unit suite contains no
`conditions` reference at all, so no CI test encodes the unconditional form.

## Hypothesized Root Cause

This is not a hypothesis in the usual sense — the cause is confirmed by reading
two lines. Recorded in the required form for consistency with the other bugfix
designs in this repo.

1. **Misplaced assignment (confirmed, primary).** `api.py:968` puts
   `"conditions": conditions if conditions is not None else [],` inside the
   common `data` dict literal, which is constructed unconditionally before any
   gate runs. The correct home, `if self._parsed_version() >= parse_version("2.0"):`,
   sits at `api.py:1200` — roughly 232 lines later, past every type-specific
   block. So this is a genuine relocation across the method body, not an
   indentation slip, and the diff will not look local.

2. **Introduced as an intentional invariant, not an oversight.** Commit
   `70138bf feat: add Uptime Kuma v2 support` added the field with the comment
   `# <-- NEW: always present, defaults to empty list`. "Always present" was
   asserted as a *property* rather than gated, and the v1 case was not
   considered. This matters for the fix: the design must consciously retract an
   invariant, not just move code.

3. **No compensating gate downstream.** Neither `_convert_monitor_input` nor
   `_check_arguments_monitor` reads the `conditions` monitor field (the
   same-named local inside `_check_arguments_monitor` is unrelated
   range-validation data), and both are module-level functions with no `self`,
   so neither could have gated it even in principle.

4. **`edit_monitor` bypasses the builder entirely.** `edit_monitor`
   (`api.py:1773`) does `data = self.get_monitor(id_)`, `data.update(kwargs)`,
   then `_call('editMonitor', data)`. It never calls `_build_monitor_data`, so a
   fix confined to the builder does not cover it. On v1 the fetched dict has no
   `conditions` key, which is why the default `edit_monitor` path is healthy
   today — but an explicit kwarg goes straight into the payload.

5. **Only `conditions` is unconditional.** Every other v2-only field is either
   inside the `>= 2.0` block or emitted only on explicit non-`None` opt-in. That
   is what makes this one a total v1 outage rather than an opt-in trap, and it is
   the distinction the policy decision below turns on.

## Cross-Spec Policy Conflict

**This section needs the user's ratification before implementation.** It is a
design-phase objection to an approved requirement, raised now because it is far
cheaper here than after implementation.

### The conflict

Requirements 2.3-2.5 of this spec (a user decision, 2026-08-01) say an explicit
`conditions` against a pre-2.0 server SHALL **raise**.

An earlier spec that is **already implemented** says the opposite for exactly
this class of field. `uptime-kuma-v2-support-backlog` requirement 13.3:

> IF connected to a v1 instance (detected version < 2.0) and v2-only monitor
> parameters are provided by the caller, THEN THE Library SHALL omit those
> parameters from the payload **without raising an error or logging a warning**

The `>= 2.0` block at `api.py:1200` implements precisely that silent omission
today for `ipFamily`, `cacheBust`, `bearer_token`, `subtype` and the rest. So the
library has a documented, shipped policy of silent omission, and this spec
proposes a raise for one field.

### Verdict: `raise` wins for `conditions`, on a severity argument

The distinguishing property is **what a silent drop costs the caller**, not
whether the field is v2-only:

- `conditions` defines the monitor's **pass/fail semantics**. Silently dropping
  it produces a monitor that was created successfully, returns
  `{'msg': 'Added Successfully.', 'monitorID': n}`, and then evaluates
  up/down against criteria the caller never agreed to. The caller has no signal
  — not in the return value, not at check time. That is a false-confidence
  monitoring failure: the tool whose entire job is to tell you when something is
  wrong quietly stops applying your definition of wrong.
- `ipFamily`, `cacheBust`, `bearer_token`, `subtype` and friends change **how**
  the check is performed. Dropping them degrades the check or makes it fail
  loudly and visibly (auth rejected, wrong address family, stale cache hit), but
  they never invert the verdict while reporting success.

Silence is acceptable when the consequence is observable. It is not acceptable
when the consequence is a monitor that lies.

### The cost, stated plainly

This makes the library's treatment of v2-only monitor params **inconsistent by
design**. A caller cannot predict raise-vs-drop from first principles; it has to
be documented field by field, and supported field by field, permanently. It also
narrows an approved, implemented requirement (13.3) — the same kind of retraction
this spec already makes to `uptime-kuma-v2-support` Property 1. That narrowing
must be recorded in 13.3's spec and in the changelog, or the next contributor
will read 13.3 as still-blanket and "fix" the raise back out.

### The seven adjacent fields (requirements 1.6 / 2.6): silent omission

Recommendation: bring `jsonPathOperator`, `snmp_v3_username`, `ping_count`,
`ping_numeric`, `ping_per_request_timeout`, `mqttWebsocketPath` and
`mqttCheckType` under the `>= 2.0` gate **silently** — no raise. Reasoning:

- They are already explicit-opt-in-only. The unconditional total-outage property
  that makes `conditions` urgent does not apply to any of them.
- Requirement 1.6 records that whether each actually fails on v1 is
  **unverified**. Raising converts an unverified, possibly-working path into a
  guaranteed hard error for callers who are fine today. That is a behaviour
  regression manufactured out of an unknown.
- Silent omission matches 13.3 and matches the block they move into, so it adds
  zero new inconsistency. A raise for all eight would multiply the blast radius
  across seven fields to fix a regression that is really about one.
- For `snmp_v3_username` the gate is close to a no-op anyway: the `SNMP` monitor
  type is itself v2-only, so a v1 server rejects the monitor type before the
  field matters. Gate it for uniformity, expect no behavioural change.

### Outcome: the raise was retained, and the inconsistency was closed the other way

**Resolved by `.kiro/specs/v2-only-fields-rule/` (issue #14), which landed.** The
`conditions` raise is **kept**, as the single named exception to a rule that now
covers the whole class. The other 25 v2-only monitor fields are still withheld and
still do not raise, but the omission is no longer silent: each withheld field is
reported by one `UnsupportedFieldWarning` per call.

So the "inconsistent by design" cost recorded below was paid down without retiring
the raise, and the severity argument in this section is what justified keeping it.
That argument is now written down as an executable test rather than prose — *a
field that changes the monitor's verdict raises; a field that changes how the check
runs is withheld with a Signal* — and a test asserts that exactly one registry
entry has the raising behaviour, so a second exception has to fail a test rather
than win an argument.

One premise of this section was also settled empirically and no longer needs to be
hedged. The recommendation for the seven adjacent fields rested partly on their v1
behaviour being **unverified**, so that raising "would convert an unverified,
possibly-working path into a guaranteed hard error". That unknown is closed: a real
1.23.2 server rejects all 25 reachable fields with `table monitor has no column
named ...`, so there was never a possibly-working path
(`.kiro/specs/v2-only-fields-rule/v1-verification-results.md`). It does not change
the conclusion — a caller who supplies such a field today still gets a working
monitor, because the library withholds it before building the payload, so raising
would still take a working call away.

### The option the requirements did not consider

There is a third position, and it is arguably the better long-term
architecture: **gate all eight silently** (restoring v1 function, matching 13.3
and the existing block exactly), and treat "tell the caller their v2-only field
was dropped" as a **separate, library-wide, consistent concern** — one uniform
signal applied to every gated field, rather than a bespoke raise bolted onto one
of them. That yields a library with one predictable rule instead of two.

Weighing it: it is more consistent, but it leaves the `conditions` silent-drop
hole open until that library-wide signal exists, and that hole is the one place
where silence is genuinely dangerous. So the recommendation is:

- **Keep 2.3-2.5's raise as approved** for `conditions`. It is the safer failure
  mode for the one field where a silent drop produces a lying monitor.
- **Gate the other seven silently**, per the section above.
- **Open a follow-up spec** for a uniform "dropped v2-only field" signal, so the
  inconsistency is explicitly temporary and tracked rather than permanent and
  accidental.

If the user prefers strict consistency with 13.3 right now, the change is
**one line**: delete the `_check_v2_only_conditions` call sites and the helper
(Change Group 2 below) and keep Change Group 1. Requirements 2.3-2.5, 2.4 and
2.5 would then need to be retracted, and Properties 2 and 3 with them. Say the
word and this design collapses to Change Groups 1, 3 and 4.

### One piece of supporting evidence for either choice

`tests/test_monitor.py::test_monitor_type_dns` (line ~186) passes an explicit
`conditions` list and — unlike its siblings `test_monitor_conditions` and
`test_monitor_dns_conditions` — has **no** `< 2.0` skip guard. On a v1 instance
it fails today with the SQLITE error; under the raise it fails with the new
`UptimeKumaException`; under silent omission its round-trip compare fails
`ABSENT`. All three are red on v1, so that test needs a `< 2.0` skip added
regardless of which policy is chosen. It is in the inherited integration suite,
so this is not a CI concern, but it belongs in the task list.

## Correctness Properties

Property 1: Bug Condition - Implicit conditions omitted on pre-2.0 servers

_For any_ input where the bug condition holds via the implicit sub-case
(`add_monitor` against a server older than 2.0 with no `conditions` argument, for
any monitor type and any combination of other parameters), the fixed
`_build_monitor_data` SHALL return a dict containing no `conditions` key, so the
add payload carries no unsupported column and the monitor is created
successfully.

**Validates: Requirements 2.1, 2.2**

Property 2: Bug Condition - Explicit conditions rejected on pre-2.0 servers

_For any_ input where the bug condition holds via the explicit sub-case (a
truthy `conditions` value reaching `add_monitor` or `edit_monitor` against a
server older than 2.0, whether supplied as a keyword argument or via
`MonitorBuilder.conditions()`), the fixed code SHALL raise `UptimeKumaException`
whose message names the `conditions` field, the required server version (2.0 or
newer) and the observed server version, and SHALL raise before any server call is
made.

**Validates: Requirements 2.3, 2.4, 2.5**

Property 3: Preservation - v2 payloads byte-identical

_For any_ input where the bug condition does NOT hold because the server is 2.0
or newer, the fixed code SHALL produce the same result as the original: the
`conditions` key present with `[]` when the argument is absent, and present with
the caller's own list object (not a copy or a fresh allocation) when a list is
supplied, with no validation of individual condition dicts.

**Validates: Requirements 3.1, 3.2, 3.8**

Property 4: Preservation - non-conditions behaviour unchanged on both majors

_For any_ input where the bug condition does NOT hold because no `conditions`
value is involved, the fixed code SHALL produce the same result as the original:
identical payloads for every other field, every existing version gate
(`parent` at 1.22, `invertKeyword` / `timeout` / `gamedigGivenPortOnly` at 1.23,
the whole `>= 2.0` block) evaluating exactly as before, `edit_monitor` still
merging `get_monitor(id_)` output and calling `editMonitor` unchanged, and
`MonitorBuilder` setters and `build()` unchanged.

**Validates: Requirements 3.4, 3.5, 3.6, 3.7**

Property 5: Preservation - type validation still precedes version handling

_For any_ input supplying `conditions` as a non-list value, the fixed
`_build_monitor_data` SHALL raise `TypeError("conditions must be a list or
None")` on both server majors, and SHALL do so before evaluating any
version-dependent handling of the field.

**Validates: Requirements 3.3**

Property 6: Preservation - adjacent v2-only fields gated without new errors

_For any_ input explicitly supplying one of the seven adjacent v2-only fields
against a server older than 2.0, the fixed code SHALL omit that field from the
payload and SHALL NOT raise, and against a 2.0-or-newer server SHALL include it
exactly as the original did.

**Validates: Requirements 2.6, 3.5**

## Fix Implementation

Small and targeted per the coding standards; no unrelated refactoring. All new
gates use `self._parsed_version()`, matching the four existing gates in this
method — never the raw `parse_version(self.version)` form.

### Change Group 1 — Relocate the `conditions` assignment (Property 1, 3)

**File**: `uptime_kuma_api/api.py`
**Function**: `_build_monitor_data`

1. **Remove** the assignment from the common dict literal. Delete `api.py:968`:
   ```python
   "conditions": conditions if conditions is not None else [],
   ```
   The literal then ends at `"httpBodyEncoding": httpBodyEncoding,`. Nothing else
   in the literal moves.
2. **Add** it as the first statement inside the existing `>= 2.0` block at
   `api.py:1200`, under the `# v2-only parameters (gated behind version check)`
   comment and before the `# Network monitors: ipFamily` sub-block:
   ```python
   # v2-only parameters (gated behind version check)
   if self._parsed_version() >= parse_version("2.0"):
       data["conditions"] = conditions if conditions is not None else []

       # Network monitors: ipFamily
       ...
   ```
3. **Copy the expression verbatim.** `conditions if conditions is not None else []`
   — not `conditions if conditions else list()`. The `is not None` form returns
   the caller's own object for both a non-empty list and an explicit `[]`; the
   PR #86 form allocates a fresh list and conflates `None` with `[]`. Declining
   that pattern is a standing instruction (backlog requirement 14.5) and
   Property 3 pins it with an identity assertion.
4. **Do not create a second `>= 2.0` block.** Reuse the existing one so
   requirement 3.4's "whole existing `>= 2.0` block" stays a single unit and the
   gate-count assumptions in the test apparatus stay true.

**On key position:** `conditions` moves from index 11 of the emitted dict to the
front of the v2 block, i.e. later in insertion order. This is not
behaviourally significant — the payload is serialised to JSON and consumed by
the server as an object, where member order carries no meaning. It is only
observable to a test that compares `list(data.keys())` or a `repr`, and no such
test exists (the v2 unit suite has no `conditions` reference at all). Recording
it so the reviewer does not have to re-derive it from the diff.

### Change Group 2 — One private guard for explicit conditions (Property 2)

Contingent on the [policy decision](#cross-spec-policy-conflict). Drop this group
if the user chooses uniform silent omission.

**File**: `uptime_kuma_api/api.py`

1. **Add a private helper** on `UptimeKumaApi`, next to `_parsed_version()`
   (~line 775) so the version-gating machinery stays together:
   ```python
   def _check_conditions_supported(self, conditions) -> None:
       """
       Rejects the v2-only ``conditions`` monitor field on a pre-2.0 server.

       Raises rather than silently dropping, because ``conditions`` defines the
       monitor's up/down semantics: a silently discarded value produces a
       monitor that reports success against criteria the caller never set.

       :raises UptimeKumaException: If conditions are requested on a server
                                    older than 2.0.
       """
       if conditions and self._parsed_version() < parse_version("2.0"):
           raise UptimeKumaException(
               "conditions requires Uptime Kuma 2.0 or newer, "
               f"but the server reports version {self.version}"
           )
   ```
   Private (leading underscore), so no new public API surface — requirement 2.7
   is satisfied. A new exception *message* is not surface.
2. **Call site A — `_build_monitor_data`**, in the validation preamble
   **immediately after** the existing `TypeError` check at `api.py:945-946`:
   ```python
   if conditions is not None and not isinstance(conditions, list):
       raise TypeError("conditions must be a list or None")

   self._check_conditions_supported(conditions)
   ```
   This placement is load-bearing for Property 5: the `TypeError` is the
   earliest validation in the method and the guard sits directly behind it, so a
   non-list value on a v1 server raises `TypeError` and never reaches the version
   check. It also means the guard can only ever see `None` or a genuine list, so
   its truthiness test is unambiguous. Keeping it in the preamble also matches
   the coding standard that validation belongs near the top of the method.
3. **Call site B — `edit_monitor`**, as the **first** statement of the method
   (`api.py:1793`, before `data = self.get_monitor(id_)`):
   ```python
   def edit_monitor(self, id_: int, **kwargs) -> dict:
       """..."""
       self._check_conditions_supported(kwargs.get("conditions"))
       data = self.get_monitor(id_)
       data.update(kwargs)
       ...
   ```
   Checking `kwargs` rather than the merged `data` is deliberate: it can only
   ever react to what the caller asked for, never to something a server echoed
   back. Placing it before `get_monitor(id_)` means no `getMonitor` round-trip is
   spent on a call that is going to fail, satisfying "before any server call is
   made". The guard itself makes no server call — `_parsed_version()` reads
   `self.version`, which reads cached `Event.INFO` data.

**Why exactly two call sites, not three.** `add_monitor` needs no change of its
own: it calls `_build_monitor_data(**kwargs)` on its first line, so call site A
covers it. Two sites cover all four routes into the server:

| Route | Covered by |
|---|---|
| `add_monitor(conditions=[...])` | A, via `_build_monitor_data` |
| `add_monitor(**builder.build())` | A, same path — `build()` emits a `conditions` kwarg |
| `edit_monitor(id_, conditions=[...])` | B |
| `edit_monitor(id_, **builder.build())` | B, same path |

**Why the guard cannot live in `MonitorBuilder`.** The builder is a
connection-less dict wrapper: `conditions()` writes `_data["conditions"]` and
`build()` returns the dict. It has no `UptimeKumaApi` reference, no
`self.version`, no `_parsed_version()`, so it cannot know the server major.
Giving it one would mean either constructing builders against a live client (a
public API change, forbidden by 2.7) or duplicating version state. Since builder
output can only reach a server through `add_monitor`/`edit_monitor`, enforcing at
that boundary covers requirement 2.4 with **zero** builder changes — which is
also what preserves 3.7.

**Why not `_check_arguments_monitor`.** It looks like the natural shared
choke point — both public methods call it — but it is a module-level function
(`api.py:253`) taking only `kwargs`, with no `self` and therefore no version
access. Converting it to a method, or threading the version into it, would touch
the shared validation path for every monitor field to gate one. Rejected as
disproportionate.

**One accepted asymmetry, recorded as a judgment call.** A *non-list truthy*
`conditions` passed to `edit_monitor` on a v1 server now raises
`UptimeKumaException` (version) where `add_monitor` would raise `TypeError`
(type). This is not a preservation break: `edit_monitor` does not raise
`TypeError` for that input today either — it forwards the value and lets the
server reject it. Adding the `isinstance` check to `edit_monitor` would be new
validation on a path requirement 3.6 says to leave alone, so it is deliberately
out of scope. The version message is still correct for such input (the field is
unsupported at any type), so nothing misleading is emitted.

### Change Group 3 — Gate the seven adjacent v2-only fields (Property 6)

**File**: `uptime_kuma_api/api.py`
**Function**: `_build_monitor_data`

These sit inside type-specific blocks, so moving them into the `>= 2.0` block
would mean duplicating their type guards. The smaller, more targeted change is
to add the version condition in place:

1. `jsonPathOperator` (`api.py:1133-1134`), inside `if type == MonitorType.JSON_QUERY`:
   ```python
   if jsonPathOperator is not None and self._parsed_version() >= parse_version("2.0"):
       data["jsonPathOperator"] = jsonPathOperator
   ```
2. `snmp_v3_username` (`api.py:1169-1170`), inside `if type == MonitorType.SNMP` —
   same shape. Expect no behavioural change in practice: the `SNMP` monitor type
   is itself v2-only, so a v1 server rejects the type before the field matters.
   Gated for uniformity.
3. `ping_count`, `ping_numeric`, `ping_per_request_timeout`
   (`api.py:1183-1191`), inside `if type == MonitorType.PING`: wrap the three
   `is not None` checks in a single nested version gate rather than repeating the
   condition three times:
   ```python
   if type == MonitorType.PING:
       if self._parsed_version() >= parse_version("2.0"):
           if ping_count is not None:
               data["ping_count"] = ping_count
           ...
   ```
4. `mqttWebsocketPath`, `mqttCheckType` (`api.py:1193-1197`), inside
   `if type == MonitorType.MQTT`: same nested-gate shape as PING.
5. **Leave the input validation unconditional.** The `ValueError` checks for
   `mqttCheckType` and `mqttWebsocketPath` length in the preamble
   (`api.py:951-956`) are argument validation, not payload emission. They must
   keep firing on both majors — a bad value is a bad value regardless of server
   version, and moving them would be a silent relaxation.
6. **No raise for any of these seven** — silent omission, per the policy
   decision. Property 6 asserts that absence of a raise explicitly, so a future
   change that adds one will fail a test rather than pass unnoticed.

**Adjacent-bug note (the standards say to look around the fix).** The monitor
*types* `RABBITMQ`, `SNMP`, `SMTP` and `SYSTEM_SERVICE` are themselves v2-only
and are not version-gated — requesting one against a v1 server sends a type the
server does not know. That is the same defect class one level up, but it is not
in this spec's requirements and it fails loudly rather than silently. Noted for a
follow-up, not fixed here.

### Change Group 4 — Documentation and record-keeping

1. `CHANGELOG.md`: a `Fixed` entry framing this as a fix to a regression **present
   in v2.1.0, v2.2.0 and v2.2.1** (introduced by `70138bf`, tags confirmed), not
   an unreleased defect (requirement 2.10).
2. Record the narrowing of `uptime-kuma-v2-support` *Property 1* (unconditional
   `conditions`) and of `uptime-kuma-v2-support-backlog` *requirement 13.3*
   (blanket silent omission), so neither reads as still-current. Per the coding
   standards' "record judgment calls".
3. No `docs/api.rst` change and no `__init__.py` export change — nothing public
   is added.
4. **Do not touch `uptime_kuma_api/__version__.py`.** Version bumping is a
   release-time decision, out of scope here.

## Testing Strategy

### Validation Approach

Two phases: first surface counterexamples against the **unfixed** code to
confirm the root cause, then verify the fix and prove v2 is untouched. All
automated tests are unit tests in `tests/test_monitor_params_v2.py` — no live
server, version mocked exactly as that file already does. Live verification is
manual and covers both majors.

**Only the explicit nine-file v2 unit list is ever run** (requirement 2.11). A
bare `pytest tests/` would drag in the inherited integration suite, which wipes
every monitor, notification, proxy, tag, status page, docker host, maintenance
window and API key on the target during setup.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing
the fix, and confirm or refute the root cause. If refuted, re-hypothesize.

**Test Plan**: Add the fix-checking tests below to
`tests/test_monitor_params_v2.py` first and run them against the unfixed code.
The file's existing idiom supplies both majors: `setUp` builds a `2.4.0` mock and
binds the real `_parsed_version` and `_build_monitor_data` to it; the
`_build_v1()` helper does the same for `1.23.2`.

**Test Cases**:

1. **Implicit omission on v1** — `_build_v1()(type=HTTP, name="t",
   url="http://x")`, assert `"conditions" not in result`. **Fails on unfixed
   code** (the key is present as `[]`).
2. **Implicit omission across monitor types on v1** — same assertion looped over
   HTTP, PING, PORT, DNS, KEYWORD, PUSH. **Fails on unfixed code** for every
   type, which is the direct evidence for "unconditional, no opt-in needed".
3. **Explicit rejection on v1** — `_build_v1()(..., conditions=[{...}])`, assert
   `UptimeKumaException` raised. **Fails on unfixed code** (no exception; the
   field is silently forwarded).
4. **Explicit rejection via `edit_monitor` on v1** — **fails on unfixed code**
   for the same reason.
5. **Explicit empty list on v1** — `conditions=[]`, assert no raise and
   `"conditions" not in result`. **Fails on unfixed code** on the second half of
   the assertion (the key is present).

**The single test that must be proven red pre-fix** (requirement 2.9) is case 1:
`test_conditions_omitted_on_v1` in a new
`TestConditionsV1Gate(unittest.TestCase)` class. It is the minimal, most direct
encoding of the regression — the default `add_monitor` path against a v1 server —
and it needs no policy decision to be valid, so it stays meaningful whichever way
the raise-vs-omit question is settled. Procedure per the testing standards: write
it, watch it fail against the unfixed code, apply Change Group 1, watch it pass,
then revert-and-recheck before the PR.

**Expected Counterexamples**:
- `"conditions": []` present in the v1 payload for every monitor type and every
  parameter combination → confirms root cause 1 (misplaced assignment at
  `api.py:968`) and root cause 5 (only this field is unconditional).
- No exception for an explicit list on v1 → confirms root cause 3 (nothing
  downstream gates it).
- The `edit_monitor` counterexample confirms root cause 4 (the builder fix does
  not reach that path), which is what justifies call site B.

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed
code produces the expected behaviour.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  IF input.conditionsArg = ABSENT THEN
    result := _build_monitor_data_fixed(input)
    ASSERT "conditions" NOT IN result                    // Property 1
  ELSE
    ASSERT RAISES UptimeKumaException, fixedPath(input)  // Property 2
    ASSERT message NAMES "conditions" AND "2.0" AND observedVersion
    ASSERT no server call was made
  END IF
END FOR
```

Case 3's message assertion checks all three required elements: the field name,
the required version, and the observed version. Case 4 asserts no server call by
mocking `get_monitor` / `_call` on the instance and asserting neither was
invoked — which also proves the guard's placement ahead of `get_monitor(id_)`.

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the
fixed code produces the same result as the original.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT F_original(input) = F_fixed(input)
END FOR
```

**Testing Approach**: The `NOT isBugCondition` domain here is "everything on v2,
plus everything on v1 that does not mention `conditions`" — far too wide to
enumerate, so the property-based style the file already uses is the right tool:
generate over monitor types and parameter combinations rather than hand-picking a
few. The existing v2 baseline is directly observable on the unfixed code, so the
preservation expectations are recorded from real behaviour, not guessed.

**Test Plan**: Observe v2 behaviour on the unfixed code, then assert the same
after the fix.

**Test Cases**:

1. **v2 default present** — observe `"conditions" == []` on unfixed v2, assert it
   still holds. (Property 3, requirement 3.1)
2. **v2 explicit passthrough with identity** — pass a list of condition dicts and
   assert `result["conditions"] is passed_list`. The `assertIs` is the point: it
   pins the no-reallocation rule that backlog requirement 14.5 states in prose,
   so a future switch to `conditions if conditions else list()` fails a test
   rather than slipping through review. (Property 3, requirements 3.2, 14.5)
3. **v2 explicit empty list identity** — `conditions=[]` on v2 yields the
   caller's own empty list, not a fresh one. Same rationale.
4. **`TypeError` ordering on both majors** — `conditions="not a list"` and
   `conditions={}` against both the `2.4.0` and `1.23.2` mocks, assert
   `TypeError` with the exact existing message. On v1 this is the ordering proof
   for Property 5: `TypeError`, not `UptimeKumaException`. **This test is the
   direct check that the designed control flow delivers requirement 3.3's
   ordering**, and it is the one that would catch the guard being placed above
   the `isinstance` check by mistake.
5. **Existing gates unmoved** — assert `parent` (1.22), `timeout` /
   `invertKeyword` (1.23) and `ipFamily` / `cacheBust` (2.0) still appear at the
   same boundaries. (Property 4, requirement 3.4)
6. **Non-`conditions` v1 payload identical** — build the same monitor on v1
   before and after, compare the dicts with `conditions` excluded. (Property 4,
   requirement 3.5)
7. **`edit_monitor` merge path untouched** — `edit_monitor(id_, interval=20)` on
   both majors with `get_monitor` and `_call` mocked, assert the merged payload
   and the `editMonitor` event are exactly as before, and that the guard did not
   interfere. (Property 4, requirement 3.6)
8. **`MonitorBuilder` unchanged** — `conditions()` still returns `self` and
   `build()` still emits only explicitly-set fields, including `conditions` when
   set. The builder is version-blind by design, so `build()` output must be
   identical on both majors. (Property 4, requirement 3.7)
9. **Adjacent fields gated, no raise** — each of the seven omitted on v1 without
   raising, present on v2 exactly as today. (Property 6, requirements 2.6, 3.5)

**Do not disturb the existing gate apparatus.** `tests/test_monitor_params_v2.py`
already carries `GATE_CONSTANTS = ["1.22", "1.23", "1.23.1", "2.0"]` (line 690)
and the `TestValidVersionGatePreservation` / `TestUnparseableVersionBugCondition`
classes that probe gate outcomes via `_monitor_gates` (line 904) and
`_assert_gated_path_runs`. Verified safe: both probes call `_build_monitor_data`
**without** a `conditions` argument, so the new guard never fires for them, and
both detect the `2.0` gate through `ipFamily` / `cacheBust` presence, which
Change Group 1 does not touch. `GATE_CONSTANTS` needs no new entry either — `2.0`
is already there and no new gate constant is introduced. **New tests go in a new
class; those two classes are not edited.**

### Unit Tests

- `conditions` omission on v1 across monitor types and parameter combinations.
- `UptimeKumaException` for an explicit truthy `conditions` on v1, via
  `_build_monitor_data`, via `add_monitor`, and via `edit_monitor`; message
  content asserted.
- `conditions=[]` on v1: no raise, key absent.
- v2 presence, passthrough and object identity.
- `TypeError` precedence over the version guard on both majors.
- The seven adjacent fields: omitted on v1 without raising, present on v2.
- Builder round-trip: `MonitorBuilder(...).conditions([...]).build()` into
  `add_monitor` raises on v1 and succeeds on v2.

### Property-Based Tests

Following the seeded-generator style already in the file (`generate_valid_pep440_versions`,
`PBT_SEED`, `PBT_CASES`) rather than introducing a new dependency — `hypothesis`
is not a project dependency.

- Over generated valid PEP440 versions: `"conditions" in payload` iff
  `parse_version(raw) >= parse_version("2.0")`. This is the version-boundary
  form of Properties 1 and 3 and covers pre-releases, post-releases,
  dev-releases and local versions around the boundary, not just plain triples.
- Over generated `MonitorType` × parameter combinations on v1: `conditions` never
  present, and no `UptimeKumaException` unless `conditions` was explicitly
  supplied truthy.
- Over generated condition-list shapes on v2: the emitted value is the same
  object that was passed in (the identity/no-reallocation property).

### Integration Tests

Inherited suite, not CI. `tests/test_monitor.py::test_monitor_type_dns` passes an
explicit `conditions` list with no version skip, unlike its two guarded siblings;
it needs a `parse_version(self.api.version) < parse_version("2.0")` skip added to
match them. It is red on v1 today regardless, so this is a correctness fix to the
test, not an accommodation of the new behaviour.

### Live Verification Plan

Requirement 2.8 is the acceptance gate: **`add_monitor()` succeeds against a live
Uptime Kuma 1.23.2 server through the real public method, with no
`pop("conditions")` workaround** — the workaround that made the original
discovery run complete. Both majors are reachable.

**v1 — disposable 1.23.2 container.** Start over `ssh <user>@<docker-host>` on host
port **3023** (3001 and 3022 are taken by existing Kuma instances; Nginx Proxy
Manager holds 80, 81 and 443):

```
ssh <user>@<docker-host> "docker run -d --name kuma-v1-conditions -p 3023:3001 louislam/uptime-kuma:1.23.2"
```

A fresh container has no admin user, so the library bootstraps it itself:
`need_setup()` returns `True`, then `setup(username, password)` creates the
account, then `login(...)`. Sequence:

1. `need_setup()` / `setup()` / `login()` against `http://<docker-host>:3023`.
2. Assert `api.version` starts with `1.23` — the whole run is meaningless if it
   is accidentally pointed at a v2 instance.
3. `add_monitor(type=MonitorType.HTTP, name="v1-conditions-gate",
   url="http://127.0.0.1")` with **no** `conditions` argument and **no**
   `pop("conditions")`. Expect `{'msg': 'Added Successfully.', 'monitorID': n}`.
   This is the acceptance criterion.
4. Round-trip: `get_monitor(n)` and confirm the created monitor matches what was
   sent — "the server didn't reject it" is not verification, per the testing
   standards.
5. Repeat step 3 for a second type (PING) to show the fix is not
   HTTP-specific.
6. `add_monitor(..., conditions=[{...}])` → expect `UptimeKumaException` naming
   the field and the required version, and confirm no monitor was created.
7. `edit_monitor(n, interval=120)` → succeeds (3.6 on a real v1 server).
8. `edit_monitor(n, conditions=[{...}])` → expect the same
   `UptimeKumaException`.
9. Teardown: `docker rm -f kuma-v1-conditions`. The container is run without a
   volume, so removing it destroys all its state; nothing is shared with the
   other instances on that host.

Steps 1-8 belong in a new manual script under `tests/` following the existing
`live_test_*.py` conventions: driven by env vars, **ASCII-only output**
(`PASS` / `FAIL` / `->`, no check marks or box-drawing — non-ASCII has crashed
scripts mid-run on the cp1252 console), and not collected by CI. It must be
pointed only at a disposable instance.

**v2 — existing 2.5.0 instance** via the `tests/.env` keys `UPTIME_KUMA_URL`,
`UPTIME_KUMA_USERNAME` and `UPTIME_KUMA_PASSWORD` (referenced by name; values
stay in the gitignored file and are never printed):

1. `python tests/live_test_backup.py` — config snapshot **first**, always.
2. `python tests/live_test_create.py` — already exercises
   `MonitorBuilder(...).conditions([...])` end to end, so it covers the v2
   builder path and the sent-vs-returned round-trip comparison
   (`ABSENT` / `MISMATCH`) for `conditions` without modification.
3. `python tests/live_test_cleanup.py --dry-run`, inspect, then
   `python tests/live_test_cleanup.py`.

**Do not add the v1 container to CI.** CI stays the nine-file unit suite; the
container run is a documented manual step recorded in the task list and the PR
description.
