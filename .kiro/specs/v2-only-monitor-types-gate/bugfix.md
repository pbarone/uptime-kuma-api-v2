# Bugfix Requirements Document

## Introduction

`MonitorType` defines four monitor types that Uptime Kuma only implements from
2.x onward: `RABBITMQ`, `SNMP`, `SMTP` and `SYSTEM_SERVICE`. Nothing in
`_build_monitor_data` or `edit_monitor` compares the requested `type` against the
server version, so a caller can ask a pre-2.0 server for a monitor type it has no
implementation of.

`pre-fix-evidence.md` establishes the provenance (all four are 2.x-only in
upstream source and appear in no 1.x tag) and, against a real 1.23.17 server,
what actually happens. That evidence **corrects issue
[#12](https://github.com/pbarone/uptime-kuma-api2/issues/12)'s premise** in a way
that matters to the design:

- The failure today is *not* the server rejecting the type. A 1.x server never
  validates `type` on the add path; `Monitor.validate()` checks interval bounds
  and nothing else. What fails is a `SQLITE_ERROR` naming a snake_case column
  (`rabbitmq_nodes`, `snmp_oid`, `smtp_security`, `system_service_name`) that the
  library sends because that type was requested.
- With those companion fields absent from the payload, a 1.23.17 server
  **accepts** the type, answers `Added Successfully.`, and creates a monitor that
  sits `PENDING` forever reporting `Unknown Monitor Type` — identically to an
  invented garbage type string.

So the current loud failure is a byproduct of the companion-field payload, not a
guarantee, and it is opaque and misattributed when it does fire.

**Scope of the fix.** A private version guard rejecting the four v2-only monitor
types on a pre-2.0 server, called from `_build_monitor_data` (covering
`add_monitor`) and from `edit_monitor`; regression tests in
`tests/test_monitor_params_v2.py`; a `CHANGELOG.md` entry under `### Unreleased`;
retirement of the 2.3.0 note that defers this defect; and annotation of the
earlier spec assertion this narrows.

**Explicitly out of scope.** The v2-only monitor *fields*
([#14](https://github.com/pbarone/uptime-kuma-api2/issues/14)) — the seven
adjacent fields the conditions spec brought under the gate silently keep that
behaviour, and no field-level signalling is introduced here. The signalling
mechanism chosen here (a plain `UptimeKumaException`) is **provisional** and may
be superseded by #14; see `design.md`. `MonitorType` itself is not changed: no
member is removed, renamed or re-valued, and no new export is added.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN `add_monitor` is called with `type=MonitorType.RABBITMQ`, `SNMP`, `SMTP` or `SYSTEM_SERVICE` against a server older than 2.0 THEN the system builds and sends the payload, and the caller receives ``UptimeKumaException: insert into `monitor` (...) - SQLITE_ERROR: table monitor has no column named <companion_column>`` — an error that names a database column rather than the unsupported type, and that arrives only after a round trip

1.2 WHEN that payload reaches a pre-2.0 server without the type's v2-only companion columns THEN the server accepts it, returns `{'msg': 'Added Successfully.', 'monitorID': n}`, and creates a monitor that remains `PENDING` indefinitely with the heartbeat message `Unknown Monitor Type`, because a 1.x server validates only interval bounds on the add path and first consults `type` at beat time

1.3 WHEN `edit_monitor(id_, type=<a v2-only type>)` is called against a server older than 2.0 THEN the system performs the same unguarded round trip, because `edit_monitor` bypasses `_build_monitor_data` entirely and its only version guard is `_check_conditions_supported`

1.4 WHEN a caller reads the library's public surface THEN nothing states that these four types require a 2.0 server, so the version requirement is discoverable only by triggering the failure

### Expected Behavior (Correct)

2.1 WHEN `add_monitor` is called with any of the four v2-only monitor types against a server older than 2.0 THEN the system SHALL raise `UptimeKumaException` before any payload is built or sent

2.2 WHEN that exception is raised THEN its message SHALL name the requested type's string value, the required version `2.0`, and the version the server actually reported, so the caller can act on it without reading library source

2.3 WHEN `edit_monitor` is called with an explicit `type` that is one of the four against a server older than 2.0 THEN the system SHALL raise the same `UptimeKumaException` before `get_monitor(id_)` or any `_call` is reached

2.4 WHEN a `MonitorBuilder` config carrying one of the four types is passed to `add_monitor` or `edit_monitor` against a pre-2.0 server THEN the system SHALL raise, with enforcement at the `add_monitor` / `edit_monitor` boundary rather than in the builder, which holds no server connection and is version-blind by design

2.5 WHEN the fix is delivered THEN it SHALL ship with regression tests in `tests/test_monitor_params_v2.py`, each demonstrated to fail against the unfixed code, and a `CHANGELOG.md` entry under the existing `### Unreleased` heading

2.6 WHEN the fix is delivered THEN the 2.3.0 changelog note deferring this defect ("Out of scope here, and it fails loudly rather than silently, which is why it is a note and not a fix") SHALL be retired, and the earlier spec assertion this narrows SHALL be annotated in place

### Unchanged Behavior (Regression Prevention)

3.1 WHEN connected to a server at 2.0 or newer THEN all four types SHALL CONTINUE TO be accepted with byte-identical payloads, including every companion field, and the guard SHALL add no key to and remove no key from any payload on either server major

3.2 WHEN connected to a server older than 2.0 and requesting any monitor type that is **not** one of the four THEN the system SHALL CONTINUE TO behave exactly as today, with no new exception and no payload change

3.3 WHEN `conditions` is supplied explicitly against a pre-2.0 server THEN `_check_conditions_supported` SHALL CONTINUE TO fire first and produce its existing message, so a call that trips both guards raises exactly what it raises today

3.4 WHEN `_check_arguments_monitor` runs THEN its `required_args_by_type` entries for the four types SHALL CONTINUE TO be enforced unchanged on both server majors, since a missing required field is a caller error regardless of server version

3.5 WHEN a caller uses the library's public surface THEN the system SHALL NOT add any public method, parameter, class or export: the guard is a private helper and the type set is a private module constant. A new exception message is not API surface

3.6 WHEN a non-list `conditions` or an out-of-range `responseMaxLength` is supplied THEN the existing `TypeError` / `ValueError` validation SHALL CONTINUE TO fire on both majors in its current order relative to the version guards

3.7 WHEN the server reports an unparseable version string THEN the new guard SHALL route through `_parsed_version()` like every other gate, so such a server is treated as newest and the four types are permitted

### Bug Condition and Properties

```pascal
FUNCTION isBugCondition(X)
  INPUT: X = (server_version, requested_type)
  OUTPUT: boolean

  RETURN X.requested_type IN {rabbitmq, snmp, smtp, system-service}
     AND X.server_version < 2.0
END FUNCTION
```

**Property: Fix Checking.** Every request meeting the bug condition is rejected
client-side, with a message naming all three facts, and nothing reaches the
server.

```pascal
// Property: Fix Checking
FOR ALL X WHERE isBugCondition(X) DO
  result <- request'(X)
  ASSERT result = UptimeKumaException
  ASSERT names(result.message, X.requested_type)
     AND names(result.message, "2.0")
     AND names(result.message, X.server_version)
  ASSERT NOT payload_built(X) AND NOT request_sent(X)
END FOR
```

**Property: Preservation Checking.** Every other input behaves identically to
today — every v2 session, every non-v2-only type on v1, and every existing
validation and gate.

```pascal
// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT F(X) = F'(X)
END FOR
```

`F` is the library before the fix, `F'` after it.
