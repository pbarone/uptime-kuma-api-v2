# Bugfix Requirements Document

## Introduction

`api.add_monitor()` fails outright against every Uptime Kuma 1.23.x server. The
server rejects the insert:

```
UptimeKumaException: insert into `monitor` (... `conditions` ...) - SQLITE_ERROR: table monitor has no column named conditions
```

`conditions` is a Uptime Kuma **2.x-only** monitor field. `_build_monitor_data`
in `uptime_kuma_api/api.py` emits it in the unconditional common `data` dict
with no version gate, so every `add_monitor` call on a v1.x server sends a
column the v1 schema does not have. No v2-specific input is required to trigger
it — the default path is enough.

This violates the project's one non-negotiable principle: backward
compatibility with Uptime Kuma v1.x is sacred, and server-version-specific
behavior must be gated behind a `parse_version` check. It affects the most-used
public method in the library.

**Discovery and blast radius.** Found incidentally on 2026-08-01 during live v1
compatibility verification for the `monitor-list-cache-staleness` spec, against
a disposable `louislam/uptime-kuma:1.23.2` container. That run only completed by
calling `_build_monitor_data(...)` then `data.pop("conditions")` before
`_call("add", data)` — the bug was worked around, not fixed. Introduced by
commit `70138bf feat: add Uptime Kuma v2 support (conditions field + status page
fix)` (2026-06-22) and **already shipped**: `git tag --contains 70138bf` returns
`v2.1.0`, `v2.2.0`, `v2.2.1`. It is also present in the unreleased 2.3.0 working
tree. The changelog entry must frame this as a fix to a released regression, not
an unreleased one.

**A previously-asserted property is deliberately narrowed.** The originating
spec `.kiro/specs/uptime-kuma-v2-support/design.md` intentionally made this
field always-present (`"conditions": [], # <-- NEW: always present, defaults to
empty list`) and encoded *Property 1: Default conditions is empty list* — "*For
any* valid monitor configuration ... where the `conditions` parameter is not
explicitly provided, `_build_monitor_data` SHALL produce a dict containing
`"conditions": []`". **That property was correct only for v2 servers and is
superseded by this spec**, which restricts it to server versions >= 2.0. This is
a legitimate, deliberate exception to the usual "don't relax an assertion" rule;
any test asserting unconditional presence is expected to need updating rather
than treated as a signal the fix is wrong. Verified during requirements:
`tests/test_monitor_params_v2.py` contains no `conditions` reference, so no unit
test currently asserts the unconditional form. The only test coverage is in the
live integration file `tests/test_monitor.py`, already guarded by
`parse_version(self.api.version) < parse_version("2.0")` skips.

**Design context settled during requirements** (recorded so later phases do not
rediscover it):

- The fix shape already exists in-file. `_build_monitor_data` has a
  `if self._parsed_version() >= parse_version("2.0"):` block near its end that
  gates every *other* v2-only field (`ipFamily`, `cacheBust`, `bearer_token`,
  `subtype`, ...). `conditions` is the lone v2-only field emitted outside it.
- `edit_monitor` does bypass `_build_monitor_data` — it merges `get_monitor(id_)`
  output and calls `_call('editMonitor', data)` directly, so on v1 the key is
  naturally absent from the fetched dict. It is **not** fully unaffected: a
  caller passing `conditions=[...]` to `edit_monitor` puts the key straight into
  that dict and reaches the same server rejection.
- `MonitorBuilder.conditions()` sets `_data["conditions"]` directly, so the
  builder feeds `add_monitor`/`edit_monitor` the same way an explicit kwarg does
  and must obey the same rule.
- Neither `_convert_monitor_input` nor `_check_arguments_monitor` reads the
  `conditions` monitor field (the same-named local in
  `_check_arguments_monitor` is unrelated range-validation data).
- **Explicit `conditions` on a v1.x server raises.** Silently dropping loses
  data the caller asked for; passing it through reproduces the SQLITE error. The
  chosen behavior is a clear `UptimeKumaException` naming the field and the
  required server version (user decision, 2026-08-01).

## Bug Analysis

### Current Behavior (Defect)

What happens today against a pre-2.0 server.

1.1 WHEN `add_monitor` is called against a 1.23.x server with no `conditions`
argument THEN the system emits `"conditions": []` in the add payload and the
server rejects the insert with `SQLITE_ERROR: table monitor has no column named
conditions`, so no monitor is created.

1.2 WHEN `add_monitor` is called against any Uptime Kuma server older than 2.0
THEN the system emits the `conditions` key unconditionally, because the
assignment in `_build_monitor_data` sits in the common `data` dict outside the
existing `>= 2.0` gate.

1.3 WHEN a caller explicitly passes `conditions=[...]` to `add_monitor` on a
pre-2.0 server THEN the system forwards the field to the server and the same
insert failure occurs, with no diagnostic naming the version requirement.

1.4 WHEN a configuration built via `MonitorBuilder.conditions(...)` is passed to
`add_monitor` on a pre-2.0 server THEN the system behaves as in 1.3, because the
builder writes `_data["conditions"]` directly.

1.5 WHEN a caller passes `conditions=[...]` to `edit_monitor` on a pre-2.0
server THEN the merged dict carries the key through to `editMonitor` and the
server rejects the update for the same reason.

1.6 WHEN a caller explicitly supplies any other v2-only monitor parameter that
is emitted outside the existing `>= 2.0` gate (`ping_count`, `ping_numeric`,
`ping_per_request_timeout`, `mqttWebsocketPath`, `mqttCheckType`,
`jsonPathOperator`, `snmp_v3_username`) on a pre-2.0 server THEN the system
forwards the field to the server, exposing the same defect class on explicit
opt-in; whether each of these actually fails on v1 is currently unverified.

### Expected Behavior (Correct)

2.1 WHEN `add_monitor` is called against a server older than 2.0 with no
`conditions` argument THEN the system SHALL omit the `conditions` key entirely
from the add payload and the monitor SHALL be created successfully.

2.2 WHEN `_build_monitor_data` runs against a server older than 2.0 THEN the
system SHALL NOT include a `conditions` key in the returned dict for any monitor
type or parameter combination, using the same
`self._parsed_version() >= parse_version("2.0")` idiom already used for the
other v2-only fields in that method.

2.3 WHEN a caller explicitly passes a non-empty `conditions` list to
`add_monitor` on a pre-2.0 server THEN the system SHALL raise
`UptimeKumaException` naming the `conditions` field and the required server
version (2.0 or newer) and the observed server version, and SHALL do so before
any server call is made.

2.4 WHEN a configuration built via `MonitorBuilder.conditions(...)` supplies a
non-empty `conditions` list on a pre-2.0 server THEN the system SHALL apply the
same rule as 2.3, so the builder path cannot bypass the gate.

2.5 WHEN a caller passes a non-empty `conditions` list to `edit_monitor` on a
pre-2.0 server THEN the system SHALL apply the same rule as 2.3 rather than
forwarding the key to `editMonitor`.

2.6 WHEN the audit required by 1.6 finds a v2-only monitor field emitted without
a version gate THEN the system SHALL bring that field under the same gating rule
within this spec's scope, since it is the same defect class found the same way.

2.7 WHEN the fix is implemented THEN the system SHALL NOT add any new public API
surface — no new public method, no new public parameter, no signature change.
This is a version gate on an existing field, not a feature.

2.8 WHEN the fix is verified THEN `add_monitor()` SHALL succeed against a live
Uptime Kuma 1.23.2 server through the real public method, with no
`pop("conditions")` workaround, and SHALL also be verified against the live
2.5.0 server.

2.9 WHEN the regression test is added THEN it SHALL live in the v2 unit suite
(`tests/test_monitor_params_v2.py` is the natural home — it already covers v2
monitor parameters and version gating) and SHALL be proven to fail against the
unfixed code before the fix lands.

2.10 WHEN the change is documented THEN `CHANGELOG.md` SHALL record it as a fix
to a regression present in v2.1.0, v2.2.0 and v2.2.1.

2.11 WHEN tests are run during this work THEN only the explicit nine-file v2 unit
list SHALL be used — a bare `pytest tests/` SHALL NOT be run, because the
inherited integration tests wipe the target instance.

### Unchanged Behavior (Regression Prevention)

v2 behavior must be byte-identical to today. Everything below holds already and
must keep holding.

3.1 WHEN `add_monitor` is called against a 2.x server with no `conditions`
argument THEN the system SHALL CONTINUE TO emit `"conditions": []` in the
payload.

3.2 WHEN `add_monitor` is called against a 2.x server with an explicit
`conditions` list THEN the system SHALL CONTINUE TO pass the list through
unchanged, with no validation of individual condition dicts.

3.3 WHEN `conditions` is supplied as a non-list value THEN the system SHALL
CONTINUE TO raise `TypeError("conditions must be a list or None")`, on both
server majors, before any version-dependent handling.

3.4 WHEN `_build_monitor_data` runs against any server version THEN the system
SHALL CONTINUE TO apply every existing version gate unchanged — `parent` at
1.22, `invertKeyword`, `timeout` and `gamedigGivenPortOnly` at 1.23, and the
whole existing `>= 2.0` block.

3.5 WHEN `add_monitor` is called against a pre-2.0 server for any monitor type
that exists in that server version THEN the system SHALL CONTINUE TO produce the
same payload it produces today for every field other than `conditions`.

3.6 WHEN `edit_monitor` is called without a `conditions` kwarg THEN the system
SHALL CONTINUE TO merge `get_monitor(id_)` output with the supplied kwargs and
call `editMonitor` exactly as today, on both server majors.

3.7 WHEN `MonitorBuilder` is used THEN the system SHALL CONTINUE TO expose the
`conditions()` setter and every other setter with unchanged signatures, and
`build()` SHALL CONTINUE TO return only explicitly-set fields.

3.8 WHEN monitors are read back via `get_monitor` or `get_monitors` THEN the
system SHALL CONTINUE TO return the server's response shape unchanged on both
server majors.

3.9 WHEN the v2 unit suite is run THEN every test that passes today SHALL
CONTINUE TO pass, with the single documented exception of any assertion of
unconditional `conditions` presence, which is superseded per the Introduction.
