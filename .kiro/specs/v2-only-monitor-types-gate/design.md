# Design

## Overview

One private guard, mirroring `_check_conditions_supported`, called from the two
places a caller can name a monitor type. Roughly ten lines of production code.

This document is short on purpose. The three existing bugfix specs run 105-145 KB
because each covers a *released* regression with a full live-verification cycle;
this is an unreleased latent defect with a decided outcome, so the reasoning that
needs writing down is the policy question and the evidence, not the mechanics.

## Policy collision — needs ratification

`.kiro/specs/conditions-field-v1-regression/design.md` `## Cross-Spec Policy
Conflict` was ratified, and it **declined to raise** for seven adjacent v2-only
fields. Two of its three reasons bear directly on #12:

> Requirement 1.6 records that whether each actually fails on v1 is
> **unverified**. Raising converts an unverified, possibly-working path into a
> guaranteed hard error for callers who are fine today. That is a behaviour
> regression manufactured out of an unknown.

#12 proposes exactly the raise that reasoning refused. So: does the evidence
discharge the objection, or does #12 contradict a ratified policy?

### Verdict: the evidence discharges the objection. #12 does not contradict the policy.

The objection was conditional, and its condition was *unverified failure*. That
condition no longer holds. `pre-fix-evidence.md` establishes that on any 1.x
server both reachable outcomes are failures:

| companion fields on the wire | 1.23.17 outcome |
|---|---|
| yes (what the library sends today) | `SQLITE_ERROR: table monitor has no column named <col>` |
| no (what a field-level gate would produce) | `Added Successfully.`, then `PENDING` forever with `Unknown Monitor Type` |

There is no third outcome, because a 1.x server contains no implementation of any
of the four types — verified in upstream source and tags, not inferred. The raise
therefore **cannot** convert a possibly-working path into a hard error. The path
does not work and cannot be made to work by any client-side choice.

Two further reasons the policy does not reach this case:

1. **13.3 is about parameters; a type is not a parameter whose loss can be
   degraded.** The ratified split turns on *what a silent drop costs the caller*:
   fields that change **how** a check runs are dropped silently, `conditions`
   raises because it changes the **verdict**. A monitor type is neither — it is
   the thing being asked for. There is nothing to drop and still have a monitor.
   The user's sequencing note already reached this: "a monitor type cannot be
   silently dropped, so #12's outcome is forced to `reject`."
2. **On severity, a type sits at or above `conditions`.** The `conditions`
   argument was that a silent drop yields "a monitor that lies" — created
   successfully, evaluating criteria the caller never set. An ungated v2-only
   type on a v1 server yields a monitor that was created successfully and
   **never evaluates anything at all**, reporting `PENDING` indefinitely. The
   library whose job is to tell you when something is wrong produces a monitor
   that will never tell you anything. That is the same failure class, one level
   up.

### What this changes in the ratified design

Nothing in its conclusions. One supporting sentence is factually wrong about
mechanism and is corrected in `pre-fix-evidence.md` `## The correction`:

> For `snmp_v3_username` the gate is close to a no-op anyway: the `SNMP` monitor
> type is itself v2-only, so a v1 server rejects the monitor type before the
> field matters.

A v1 server does not reject the type. It rejects `snmp_oid`, and only because
`snmp_oid` is sent. The conclusion (gate it, expect no behavioural change) holds;
the reason given for it does not.

### And it makes the type gate independently load-bearing

This is the finding that most affects sequencing, and it argues for #12 shipping
*ahead* of #14 rather than merely alongside it. Today's loud failure is a
byproduct of the companion-field payload. If #14 gates v2-only fields silently —
its most likely outcome, and what 13.3 already prescribes for fields — that
byproduct disappears, and these four calls stop failing and start succeeding into
permanently-`PENDING` monitors. The type gate is what prevents #14 from opening a
silent hole. Landing #12 first means #14 can choose freely for fields without
having to reason about types at all.

## Signalling is provisional

The guard raises a plain `UptimeKumaException`. This is recorded as
**provisional** and may be superseded by #14.

If #14 introduces a finer-grained exception subclassing `UptimeKumaException` (as
`Timeout` already does), every `except UptimeKumaException` catcher written
against this fix keeps working, so narrowing the type later is additive rather
than breaking. That is why shipping the coarse signal now costs nothing later.

What is *not* provisional is the decision to reject rather than proceed. #14 may
change the exception class or add a field-level signal; it cannot make an
unsupported monitor type work.

## Why the gate is 2.0 and not per-type

`SYSTEM_SERVICE` first appears in **2.1.0**, not 2.0.0 — stricter than the gate
this fix applies. A per-type floor was considered and rejected:

- The declared purpose (`product.md`) is that **v1.x compatibility is sacred**.
  The 2.0 boundary is the one the whole codebase gates on, and it fully covers
  the v1 defect this spec exists to fix.
- A `SYSTEM_SERVICE` request against a 2.0.x server fails the same way an
  ungated v1 request does, so a 2.1 floor would be a real improvement — but it is
  a *new* narrowing for v2 users, not a v1 regression fix, and it would make this
  the only per-type version floor in the library. That is scope creep into #14's
  territory (one rule for v2-only things) and belongs there.
- Recorded here rather than dropped, so the follow-up inherits the fact rather
  than rediscovering it.

> **Corrected pointer: the `SYSTEM_SERVICE` floor is owned by
> [#28](https://github.com/pbarone/uptime-kuma-api2/issues/28), not by #14.**
> #14 turned out to be scoped to v2-only *fields*, on the same reasoning this
> document uses to justify raising for a type: a type is not a parameter whose
> loss can be degraded, so it does not belong in a field-policy spec. #28 is the
> issue that carries the per-type floor map and the 2.1 floor for
> `system-service`. #14 shipped as `.kiro/specs/v2-only-fields-rule/` and
> touches no monitor type.
>
> One fact from #14's own dependency is worth carrying here, because it changes
> what a naive 2.1 floor would do: under PEP 440 a pre-release sorts below its
> release, so a `>= 2.1` gate would have rejected tag `2.1.0-beta.1` — the very
> build that first carried `system-service`. That was fixed library-wide in
> [#30](https://github.com/pbarone/uptime-kuma-api2/issues/30), which compares on
> the release segment, so #28 inherits a comparison that handles it.

## Implementation

### Change 1 — private module constant, `uptime_kuma_api/api.py`

At module scope beside the other module-level helpers, not exported from
`__init__.py`:

```python
# Monitor types Uptime Kuma only implements from 2.x onward. Each was added
# after the 1.23 line closed and appears in no 1.x tag; a pre-2.0 server has no
# implementation of any of them. Provenance and observed v1 behaviour:
# .kiro/specs/v2-only-monitor-types-gate/pre-fix-evidence.md
_V2_ONLY_MONITOR_TYPES = frozenset({
    MonitorType.RABBITMQ,
    MonitorType.SNMP,
    MonitorType.SMTP,
    MonitorType.SYSTEM_SERVICE,
})
```

`MonitorType` is a `str` Enum, and `str.__hash__` is inherited, so membership
works for both an enum member and a bare `"snmp"` string — confirmed by
experiment rather than assumed. A caller who passes the raw string is gated
identically.

### Change 2 — the guard, mirroring `_check_conditions_supported`

```python
    def _check_monitor_type_supported(self, type_) -> None:
        """
        Rejects a v2-only monitor type on a pre-2.0 server.

        Raises rather than proceeding, because a monitor type is not a parameter
        whose loss can be degraded: it is the thing being requested. A pre-2.0
        server has no implementation of these types and does not validate the
        type on the add path, so an ungated request either fails with an opaque
        SQLITE_ERROR naming a database column, or -- once the type's v2-only
        companion fields are gated -- succeeds into a monitor that stays PENDING
        forever reporting "Unknown Monitor Type".

        :param type_: The caller-supplied monitor type, or None.
        :raises UptimeKumaException: If a v2-only type is requested on a server
                                     older than 2.0.
        """
        if type_ in _V2_ONLY_MONITOR_TYPES and self._parsed_version() < parse_version("2.0"):
            raise UptimeKumaException(
                f"monitor type '{MonitorType(type_).value}' requires Uptime Kuma "
                f"2.0 or newer, but the server reports version {self.version}"
            )
```

`MonitorType(type_).value` rather than interpolating `type_` directly: str-Enum
`__format__` has changed across Python 3.8-3.13, and the message must read
`'snmp'` on every supported interpreter, not `MonitorType.SNMP` on some of them.
The construction is safe because the line is only reached when `type_` is already
a known member.

### Change 3 — two call sites

`_build_monitor_data`, immediately **after** the existing conditions guard:

```python
        self._check_conditions_supported(conditions)
        self._check_monitor_type_supported(type)
```

Order matters and is deliberate: the conditions guard keeps its current position,
so a call that trips both (`add_monitor(type=SNMP, conditions=[...])` on v1)
raises exactly the message it raises today. Requirement 3.3. Putting the type
check first would arguably be more useful to that caller, but it would change
existing observable behaviour to no benefit for the defect being fixed.

`edit_monitor`, beside its existing conditions guard:

```python
        self._check_conditions_supported(kwargs.get("conditions"))
        self._check_monitor_type_supported(kwargs.get("type"))
```

`kwargs.get("type")`, not the merged `data["type"]`: the guard must fire on what
the **caller explicitly asked for**. Reading the merged value would raise on
`edit_monitor(id_, interval=120)` for a monitor that already carries one of these
types — which on a v1 server cannot happen, but on an unparseable-version or
mixed-fleet path would be a spurious failure on a call the caller never made a
v2-only request in.

### Scope note for ratification

Issue #12 names only `_build_monitor_data`. `edit_monitor` is included anyway,
because `_check_conditions_supported` — the pattern #12 asks this to mirror — is
called from both, and because the alternative is an inconsistency a caller meets
immediately: `add_monitor(type=SNMP)` raising while
`edit_monitor(id, type=SNMP)` does not. One extra line.

## Testing Strategy

`tests/test_monitor_params_v2.py`, alongside the existing conditions-gate
classes. **No new test file:** the CI unit-file list is duplicated across
`CONTRIBUTING.md`, `AGENTS.md`, `.github/workflows/test.yml`, `run_tests.sh` and
the steering files, and adding a tenth file means editing all of them. That drift
hazard is documented in `git-and-releasing.md` and has bitten this project
repeatedly.

Two classes, following the file's existing idiom (a `MagicMock(spec=UptimeKumaApi)`
with the real `_parsed_version` and the real guards bound onto it, so the gate
parses `self.version` for real):

- **`TestV2OnlyMonitorTypesV1Gate`** — the bug condition. All four types raise on
  v1 via `_build_monitor_data`; the message names the type string, `2.0` and the
  observed version; `edit_monitor` raises before `get_monitor` or `_call`;
  a `MonitorBuilder` config raises at the `add_monitor` boundary; a raw `"snmp"`
  string is gated like the enum member.
- **`TestV2OnlyMonitorTypesPreservation`** — the preservation half. All four
  accepted on v2 with their companion fields intact; non-v2-only types unaffected
  on v1; the conditions guard still wins when both apply; an unparseable version
  permits the types; `MonitorType` membership unchanged.

Per `testing.md`, every bug-condition test is run against the unfixed code first
and confirmed red before the fix lands. The preservation tests are expected green
both before and after — that is what they are for.

Live verification is **not** part of this spec. The evidence run in
`pre-fix-evidence.md` already establishes the v1 behaviour the fix responds to,
and the fix's effect is a client-side raise that never reaches a server, so there
is nothing a live round trip could observe that a unit test cannot. No new
`live_test_*.py` script is added.
