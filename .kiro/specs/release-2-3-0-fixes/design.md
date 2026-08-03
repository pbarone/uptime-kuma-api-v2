# Release 2.3.0 Fixes Bugfix Design

## Overview

This design formalises the "2.3.0 batch" of fixes for the `uptime-kuma-api2`
library (import package `uptime_kuma_api`). It bundles five confirmed library
defects plus a behaviour-neutral docs/metadata sweep. Each defect is treated as
an independent **bug condition** `C(X)` with a paired **fix check** (the bug is
corrected for inputs that satisfy `C`) and **preservation check** (behaviour is
unchanged for every input that does not, i.e. `F(X) = F'(X)` for `¬C(X)`).

The overriding constraint is the project's one non-negotiable: backward
compatibility with Uptime Kuma v1.x (1.17+ through 2.x from one codebase) is
sacred. Every fix below is corrective or additive; no public method signature,
return shape, or exported symbol changes. The fixes are small and targeted, and
each ships with a regression test proven to fail against the unfixed code (per
`AGENTS.md` and the testing steering).

The six items and their confirmed code sites (verified against the current
`api.py`, which has drifted from the pre-2.2.1 line refs in `UPSTREAM_TRIAGE.md`
section 5):

| Bug | Issue / PR | Site(s) confirmed |
|-----|-----------|-------------------|
| A | #91 / PR #92 | seven `delete_*` guards: `delete_monitor` (~1558), `delete_notification` (~1966), `delete_proxy` (~2128), `delete_tag` (~2938), `delete_docker_host` (~3533), `delete_maintenance` (~3895), `delete_api_key` (~4208) |
| B | #65 / PR #81 | `__init__` builds `sio_kwargs = {"ssl_verify": ssl_verify}` (~483) but never stores `self.ssl_verify`; `get_status_page` `requests.get(...)` (~2237) has no `verify=` |
| C | #68 | `add_monitor_tag` (~1740) and `delete_monitor_tag` (~1783) assign into `_event_data[MONITOR_LIST]` which is initialised to `None` (~489) |
| D | #74 | `version` property (~696) returns the raw server string; ~10 `parse_version(self.version)` gate sites feed it into `packaging.version.parse` |
| E | #44 | `_call` (~560) wraps a bare `self.sio.call(...)` with no `try/except` |
| F | #78, #80, #60, #69, #57 | class docstring example (~424, ~442) missing `MonitorType` import and `monitorId` mis-cased at ~430; `smtpSecure` metadata in `notification_providers.py`; `notificationIDList` declared-type default; auth docs |

## Glossary

- **Bug_Condition (C)**: The set of inputs that trigger a given defect. Each bug
  has its own `isBugCondition_X`.
- **Property (P)**: The desired behaviour of the fixed function on inputs where
  `C` holds.
- **Preservation**: For all inputs where `C` does NOT hold, the fixed function
  `F'` produces the same result as the original `F`. This is where backward
  compatibility with v1.x lives.
- **F / F'**: The original (unfixed) function / the fixed function.
- **`delete_*` guard**: The idiom `if id_ not in [i["id"] for i in self.get_X()]: raise UptimeKumaException("... does not exist")` used before sending a delete to the server.
- **`_event_data[MONITOR_LIST]`**: The cached monitor-list map, initialised to
  `None` in `__init__` and populated by the `monitorList` socket.io event.
- **Version gate**: A `parse_version(self.version) >= parse_version("X.Y")`
  comparison that switches server-version-specific behaviour.
- **`self.version`**: Public property returning the server's reported version
  string via `info()`. Its return value is part of the public contract.
- **`Timeout`**: The library's own exception (`exceptions.py`), a subclass of
  `UptimeKumaException`.

## Bug Details

### Bug A — string/int id guard (#91)

The guard compares the caller-supplied `id_` against a list of integer ids. A
string id whose numeric value matches an existing entity (e.g.
`delete_monitor("371")` when monitor 371 exists) fails the membership test and
raises `"... does not exist"`, so the delete is never sent. The identical idiom
appears at all seven sites.

**Formal Specification:**
```
FUNCTION isBugCondition_A(input)
  INPUT: input = (site, id_) where site is one of the seven delete_* methods
  OUTPUT: boolean

  RETURN entityExists(site, coerceInt(id_))
         AND (id_ NOT IN storedIds(site))   // storedIds are ints; a str id_ fails
END FUNCTION
```

**Examples:**
- `delete_monitor("371")` where monitor 371 exists → raises `"monitor does not exist"` (bug); expected: monitor deleted.
- `delete_notification("5")` where notification 5 exists → raises `"notification does not exist"` (bug); expected: deleted.
- `delete_monitor(371)` (int) where monitor 371 exists → deletes correctly (NOT a bug; preserved).
- `delete_monitor("999")` / `delete_monitor(999)` where 999 is absent → raises `"monitor does not exist"` (NOT a bug; preserved).

### Bug B — `ssl_verify` ignored by `get_status_page` (#65)

`__init__` passes `ssl_verify` only into the `socketio.Client(**sio_kwargs)`
construction and never stores it on the instance. `get_status_page` then makes a
plain `requests.get(f"{self.url}/api/status-page/{slug}", timeout=self.timeout)`
with no `verify=` argument, so a caller that constructed the API with
`ssl_verify=False` still gets TLS verification on the HTTP fetch and fails
against a self-signed certificate.

**Formal Specification:**
```
FUNCTION isBugCondition_B(input)
  INPUT: input = api instance performing a get_status_page HTTP fetch
  OUTPUT: boolean

  RETURN input.performsRequestsGet AND input.ssl_verify = False
END FUNCTION
```

**Examples:**
- `UptimeKumaApi(url, ssl_verify=False).get_status_page("slug")` against a self-signed server → `requests.exceptions.SSLError` (bug); expected: page fetched with `verify=False`.
- Default `ssl_verify=True` against a trusted server → same status-page dict as before (NOT a bug; preserved).

### Bug C — monitor-list cache write crash (#68)

`add_monitor_tag` (unconditionally) and `delete_monitor_tag` both execute
`self._event_data[Event.MONITOR_LIST][str(monitor_id)] = self.get_monitor(monitor_id)`
to patch the cache, because the `monitorList` event does not carry updated tags.
When the cache has never been populated it is still `None`, so the item
assignment raises `TypeError: 'NoneType' object does not support item assignment`.
`add_status_page` already solves the mirror problem with an explicit `None`
guard; the tag methods do not.

**Formal Specification:**
```
FUNCTION isBugCondition_C(input)
  INPUT: input = (op, cacheState) where op IN {add_monitor_tag, delete_monitor_tag}
  OUTPUT: boolean

  RETURN cacheState[MONITOR_LIST] = None
END FUNCTION
```

**Examples:**
- `add_monitor_tag(tag_id, monitor_id)` when `_event_data[MONITOR_LIST]` is `None` → `TypeError` (bug); expected: completes without raising.
- `delete_monitor_tag(...)` when the cache is already populated → updates cache, returns server response (NOT a bug; preserved).

### Bug D — non-PEP440 server versions crash version gates (#74)

The `version` property returns the raw server string. Roughly ten gate sites do
`parse_version(self.version) >= parse_version("X.Y")`. A nightly build string
such as `2.0.0-dev-nightly-20240101` is not PEP440-parseable and
`packaging.version.parse` raises `InvalidVersion`, breaking every version-gated
code path against such a server.

**Formal Specification:**
```
FUNCTION isBugCondition_D(input)
  INPUT: input = raw server version string
  OUTPUT: boolean

  RETURN NOT isPep440Parseable(input)
END FUNCTION
```

**Examples:**
- Server reports `2.0.0-dev-nightly-...` → gate raises `InvalidVersion` (bug); expected: treated as newest, gate returns a usable result, never raises.
- Server reports garbage `"not-a-version"` → `InvalidVersion` (bug); expected: treated as newest.
- Server reports `2.4.0` or `1.23.2` (valid PEP440) → gates exactly as before (NOT a bug; preserved — v1.x gating must stay correct).

### Bug E — socket.io timeout leaks wrong exception type (#44)

`_call` executes `r = self.sio.call(event, data, timeout=self.timeout)` with no
`try/except`. On timeout it leaks `socketio.exceptions.TimeoutError`, which does
NOT subclass `UptimeKumaException`, so callers catching the library hierarchy
(`UptimeKumaException` / `Timeout`) miss it. Elsewhere the library already
raises its own `Timeout` for waits (`wait_for_event`, `_get_event_data`) and
translates `requests` timeouts in `get_status_page`; `_call` is the gap.

**Formal Specification:**
```
FUNCTION isBugCondition_E(input)
  INPUT: input = a _call invocation
  OUTPUT: boolean

  RETURN raises(input, socketio.exceptions.TimeoutError)
END FUNCTION
```

**Examples:**
- `_call` where the underlying `sio.call` times out → propagates `socketio.exceptions.TimeoutError` (bug); expected: raises library `Timeout` (an `UptimeKumaException`).
- `_call` that succeeds → returns the same `{"ok"}`-unwrapped result as before (NOT a bug; preserved).
- `_call` where `sio.call` raises a non-timeout error → surfaces unchanged (NOT a bug; preserved — only `TimeoutError` is translated).

### Bug F — docs and metadata defects (#78, #80, #60, #69, #57)

Static defects with no intended runtime behaviour change:

- **#78** — the `UptimeKumaApi` class docstring example references
  `MonitorType.HTTP` in both the `>>>` example (~424) and the context-manager
  `code-block` (~442), but the shown imports only import `UptimeKumaApi`
  (`>>> from uptime_kuma_api import UptimeKumaApi` and
  `from uptime_kuma_api import UptimeKumaApi`). Copy-pasting the example raises
  `NameError: name 'MonitorType' is not defined`. (README's context-manager
  example already imports `MonitorType`.)
- **#80** — the same class docstring's `add_monitor` example return shows
  `'monitorId': 1` (~430) with lowercase `d`. The real server return key is
  `monitorID`, as the `add_monitor` docstring itself shows correctly at ~1679.
- **#60/#73** — no documentation states that the Uptime Kuma UI "API key"
  cannot authenticate this socket.io API (UI API keys are `/metrics`-only).
- **#69** — `notification_providers.py` declares `smtpSecure=dict(type="str", required=False)`
  inside the `SMTP` provider table; upstream `SMTP.vue` treats it as a boolean.
- **#57** — the declared default for `notificationIDList` metadata is `{}`
  (a dict) where the declared type is a list, so it should read `[]`. This is a
  **metadata/declared-type** correction only and must NOT touch the runtime
  conversion at `api.py` ~123 (`dict_notification_ids = {}`), which builds the
  `{id: True}` map the server actually expects.

**Formal Specification:**
```
FUNCTION isBugCondition_F(input)
  INPUT: input = a documentation example OR a metadata declaration
  OUTPUT: boolean

  RETURN exampleFailsToRun(input) OR metadataTypeIncorrect(input)
END FUNCTION
```

**Examples:**
- Class docstring example run verbatim → `NameError` on `MonitorType` (bug); expected: runs (import present).
- Reading `'monitorId'` from an `add_monitor` result → `KeyError` (the real key is `monitorID`) (bug); expected: docs show `monitorID`.
- SMTP metadata consumer reads `smtpSecure` type → `"str"` (bug); expected: `"bool"`.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors (what must NOT change):**

- **Bug A**: integer-id deletes for existing entities still delete; genuinely
  absent ids (string or int) still raise the existing `"... does not exist"`
  exception and send no delete. The `id_` type sent to the server for the valid
  path must remain what the server accepts (integer).
- **Bug B**: default `ssl_verify=True` still verifies SSL for both the socket.io
  connection and the HTTP fetch; `get_status_page` returns the identical dict
  structure and fields (including the `incident`/`incidents` dual-key shape).
- **Bug C**: when the monitor-list cache is already populated, both tag methods
  update the cache and return exactly as before.
- **Bug D**: valid PEP440 versions gate exactly as before, keeping v1.17+ vs
  v2.x switching correct; the public `self.version` property continues to return
  the raw server string unchanged.
- **Bug E**: successful `_call` returns the same `{"ok"}`-unwrapped result;
  non-timeout errors surface unchanged.
- **Bug F**: every public method keeps the same signature and return shape; the
  `{}`→`[]` change is declared-type only and the effective `notificationIDList`
  payload sent for a monitor is unchanged; accepted `smtpSecure` values are
  unchanged.

**Scope:**
All inputs that do NOT satisfy each `isBugCondition_X` are completely unaffected.
This explicitly includes mouse-free concerns like: int-id deletes, trusted-cert
fetches, populated caches, valid version strings, successful and non-timeout
calls, and all runtime notification/SMTP payloads.

The desired correct behaviour for buggy inputs is defined per-bug in the
Correctness Properties section below.

## Hypothesized Root Cause

1. **Bug A — type-blind membership test.** `id_ not in [i["id"] for i in self.get_X()]`
   compares across types. Python's `"371" == 371` is `False`, so a numeric
   string never matches an integer id. The value forwarded to `_call` is the raw
   `id_`. Root cause: no coercion at the guard or the send. Confirmed present
   verbatim at all seven sites.

2. **Bug B — instance state never stored.** `ssl_verify` is a local turned into
   `sio_kwargs` and dropped; `self.ssl_verify` does not exist, and the lone
   `requests.get` omits `verify=`. Root cause: the HTTP path was never wired to
   the constructor flag. (`get_status_page` is the only `requests.get` in the
   module — confirmed by search — so it is the only HTTP site to fix, though the
   stored attribute makes any future HTTP call correct too.)

3. **Bug C — missing None-guard before item assignment.** The cache starts
   `None` and the tag methods write into it directly. `add_status_page` proves
   the intended pattern (guard-then-assign); the tag methods predate/omit it.

4. **Bug D — raw string into a strict parser at many sites.** `parse_version`
   raises on non-PEP440 input, and the raw string is parsed ~10 times. Root
   cause: no normalisation choke point; unparseable versions were never
   considered.

5. **Bug E — no exception translation in `_call`.** The socket.io transport
   raises its own `TimeoutError`, outside the library hierarchy, and `_call`
   does not translate it the way the wait helpers and `get_status_page` do.

6. **Bug F — documentation/metadata drift.** Examples were written without the
   `MonitorType` import; the return-key casing and the `smtpSecure`/
   `notificationIDList` declarations drifted from the server/upstream truth.
   These are static defects (`notification_providers.py` metadata also drives
   the required-arg check and Sphinx docstring generation, and is consumed by
   the downstream Ansible collection, so the declared type matters there too).

## Correctness Properties

Property 1: Bug A Fix — id type coercion deletes matching entities

_For any_ input where `isBugCondition_A` holds (an entity exists whose id equals
the numeric value of a string `id_` at any of the seven `delete_*` sites), the
fixed method SHALL resolve the entity via a type-coerced membership check, send
the coerced id to the server, and delete the entity without raising.

**Validates: Requirements 2.1, 2.2**

Property 2: Bug A Preservation — int ids work, absent ids still raise

_For any_ input where `isBugCondition_A` does NOT hold (an integer id for an
existing entity, or any id — string or int — that does not correspond to an
existing entity), the fixed method SHALL produce the same result as the original:
existing int-id deletes succeed, and absent ids raise the existing
`"... does not exist"` exception with no delete sent.

**Validates: Requirements 2.3, 3.1, 3.2**

Property 3: Bug B Fix — `verify` forwarded when `ssl_verify=False`

_For any_ input where `isBugCondition_B` holds (a `get_status_page` HTTP fetch on
an instance constructed with `ssl_verify=False`), the fixed code SHALL call
`requests.get` with `verify=False`.

**Validates: Requirements 2.4, 2.5**

Property 4: Bug B Preservation — default still verifies, shape unchanged

_For any_ input where `isBugCondition_B` does NOT hold (default `ssl_verify=True`),
the fixed code SHALL call `requests.get` with `verify=True` and return a status
page dict with the same structure and fields as the original.

**Validates: Requirements 3.3, 3.4**

Property 5: Bug C Fix — no crash when the cache is `None`

_For any_ input where `isBugCondition_C` holds (`add_monitor_tag` or
`delete_monitor_tag` while `_event_data[MONITOR_LIST]` is `None`), the fixed
method SHALL initialise the cache first and complete without raising `TypeError`.

**Validates: Requirements 2.6**

Property 6: Bug C Preservation — populated cache behaves identically

_For any_ input where `isBugCondition_C` does NOT hold (cache already populated),
the fixed method SHALL produce the same result and cache state as the original.

**Validates: Requirements 3.5**

Property 7: Bug D Fix — unparseable version treated as newest, never raises

_For any_ input where `isBugCondition_D` holds (a non-PEP440 / unparseable server
version), the version-gate choke point SHALL return a usable comparable that
compares as newest for every gate, and SHALL never raise `InvalidVersion`.

**Validates: Requirements 2.7, 2.8**

Property 8: Bug D Preservation — valid versions gate exactly as before

_For any_ input where `isBugCondition_D` does NOT hold (a valid PEP440 version),
the gate SHALL evaluate identically to the original `parse_version(self.version)`
comparison, and the public `self.version` property SHALL still return the raw
string.

**Validates: Requirements 3.6**

Property 9: Bug E Fix — timeout re-raised as library `Timeout`

_For any_ input where `isBugCondition_E` holds (`_call`'s underlying
`sio.call` raises `socketio.exceptions.TimeoutError`), the fixed `_call` SHALL
raise the library's `Timeout`, which is an instance of `UptimeKumaException`.

**Validates: Requirements 2.9**

Property 10: Bug E Preservation — success and non-timeout errors unchanged

_For any_ input where `isBugCondition_E` does NOT hold (a successful call, or a
non-timeout error), the fixed `_call` SHALL return the same `{"ok"}`-unwrapped
result as the original, or surface the non-timeout error unchanged.

**Validates: Requirements 3.7, 3.8**

Property 11: Bug F Fix — examples run and metadata types are correct

_For any_ input where `isBugCondition_F` holds (a doc example that fails to run
or a metadata declaration with the wrong type), the fixed artifact SHALL run
without `NameError`/`KeyError` (docs) or declare the correct type (`smtpSecure`
`"bool"`, `notificationIDList` default `[]`), and the auth docs SHALL state the
UI API key cannot authenticate this API.

**Validates: Requirements 2.10, 2.11, 2.12, 2.13, 2.14**

Property 12: Bug F Preservation — runtime behaviour and shapes unchanged

_For any_ input where `isBugCondition_F` does NOT hold (any runtime call), the
fixed code SHALL produce the same method signatures, return shapes, effective
`notificationIDList` payload, and accepted `smtpSecure` values as the original.

**Validates: Requirements 3.9, 3.10, 3.11**

## Fix Implementation

Assuming the root-cause analysis is correct (each is confirmed in code above).
Per the coding standards, changes are small and targeted; unrelated code is not
refactored alongside a fix.

### Bug A — generalise the id guard across seven sites

**File**: `uptime_kuma_api/api.py`

**Functions**: `delete_monitor`, `delete_notification`, `delete_proxy`,
`delete_tag`, `delete_docker_host`, `delete_maintenance`, `delete_api_key`.

**Changes**:
1. Apply one consistent pattern at every site: coerce the id for BOTH the
   membership check and the value sent to the server. Concretely, resolve a
   coerced id up front, e.g.:
   ```python
   ids = [i["id"] for i in self.get_monitors()]
   try:
       id_ = int(id_)
   except (TypeError, ValueError):
       pass  # non-numeric -> cannot match int ids, falls through to "does not exist"
   if id_ not in ids:
       raise UptimeKumaException("monitor does not exist")
   return self._call('deleteMonitor', id_)
   ```
2. The coercion is defensive: a non-numeric string cannot match integer ids, so
   it still raises `"... does not exist"` (preserving 2.3/3.2) rather than
   leaking a `ValueError`. This keeps the library's own-exception contract.
3. Send the coerced (integer) `id_` to `_call`, so the server receives the type
   it expects (preserving the int-id path, 3.1).
4. Keep each site inside its existing `with self.wait_for_event(...)` block
   (where present) and its existing entity accessor; do not alter the guard's
   `slug`-based sibling `delete_status_page` (it keys on `slug`, not `id`, and is
   out of scope for this bug).

**Adjacent check (expect adjacent bugs):** confirm no other method forwards a
raw caller id where the server expects an int without a guard; if found, note
it, but do not expand scope without evidence.

### Bug B — store and forward `ssl_verify`

**File**: `uptime_kuma_api/api.py`

**Changes**:
1. In `__init__`, store the flag before building `sio_kwargs`:
   `self.ssl_verify = ssl_verify`. Continue passing it into `socketio.Client`
   exactly as now (no change to the socket.io path).
2. In `get_status_page`, add `verify=self.ssl_verify` to the `requests.get`
   call, leaving `timeout=self.timeout` and the existing `Timeout` translation
   intact.
3. `get_status_page` is the only `requests.get` in the module; the stored
   attribute also makes any future HTTP call correct.

### Bug C — guard the monitor-list cache write

**File**: `uptime_kuma_api/api.py`

**Functions**: `add_monitor_tag`, `delete_monitor_tag`.

**Changes**:
1. Before the `self._event_data[Event.MONITOR_LIST][str(monitor_id)] = ...`
   assignment in each method, mirror the `add_status_page` pattern:
   ```python
   if self._event_data[Event.MONITOR_LIST] is None:
       self._event_data[Event.MONITOR_LIST] = {}
   ```
2. No other logic changes; the populated-cache path is untouched (preserving 3.5).

### Bug D — normalise version parsing behind one choke point

**File**: `uptime_kuma_api/api.py`

**Changes**:
1. Add a private choke point that parses once and tolerates unparseable input,
   e.g.:
   ```python
   def _parsed_version(self) -> Version:
       try:
           return parse_version(self.version)
       except InvalidVersion:
           return parse_version("9999")  # treat unparseable as newest
   ```
   (Import `Version` / `InvalidVersion` from `packaging.version`; `parse` is
   already imported as `parse_version`.)
2. Replace every gate expression `parse_version(self.version) >= parse_version("X.Y")`
   with `self._parsed_version() >= parse_version("X.Y")` at all ~10 sites.
3. **Judgment call (recorded per coding-standards rule 5):** the public
   `version` property is deliberately left returning the raw server string, and
   the choke point is a private accessor. Requirement 2.7 names "the version
   property" as the choke point; this design places normalisation in a dedicated
   private accessor instead so the public `version` return value stays a raw,
   unchanged contract (Property 8 / 3.6). "Newest" is realised with a max
   sentinel so all `>=` gates evaluate `True`. This decision belongs in the
   CHANGELOG.
4. Valid versions flow through `parse_version` unchanged, so v1.x vs v2.x gating
   is bit-for-bit identical (preserving 3.6).

### Bug E — translate socket.io timeouts in `_call`

**File**: `uptime_kuma_api/api.py`

**Function**: `_call`.

**Changes**:
1. Wrap only the transport call:
   ```python
   try:
       r = self.sio.call(event, data, timeout=self.timeout)
   except socketio.exceptions.TimeoutError as e:
       raise Timeout(e)
   ```
2. Leave the existing `{"ok"}` unwrapping and return path unchanged (preserving
   3.7). Only `TimeoutError` is caught, so non-timeout errors propagate unchanged
   (preserving 3.8). `Timeout` is already imported and subclasses
   `UptimeKumaException`, so existing handlers keep working.

### Bug F — docs and metadata sweep

**Files**: `uptime_kuma_api/api.py` (docstrings), `uptime_kuma_api/notification_providers.py`,
and the relevant docs source (`README.md` / `docs/` / auth docstring).

**Changes**:
1. **#78** — in the `UptimeKumaApi` class docstring, change the shown imports to
   `from uptime_kuma_api import UptimeKumaApi, MonitorType` in both the `>>>`
   example and the context-manager `code-block`.
2. **#80** — change `'monitorId': 1` to `'monitorID': 1` (~430) in the class
   docstring example to match the real return key and the `add_monitor`
   docstring at ~1679.
3. **#60/#73** — add a short note (auth-related docstring and/or README) stating
   the UI "API key" cannot authenticate this socket.io API (it is `/metrics`-only).
4. **#69** — change `smtpSecure=dict(type="str", required=False)` to
   `type="bool"` in the `SMTP` provider table, verified against upstream
   `SMTP.vue`.
5. **#57** — locate the metadata declaration whose `notificationIDList` default
   is `{}` and change it to `[]`. **Reproduce-before-fixing applies:** the
   runtime conversion at `api.py` ~123 (`dict_notification_ids = {}`) is the
   server payload builder and MUST NOT change (preserving 3.10). If the `{}`
   declared-type default is not present in the current tree, the fix is a
   verification no-op and this is recorded — the change is declared-type only.
6. Any docstring touched that contains backslashes must remain/become a raw
   string (`r"""`) to avoid `SyntaxWarning` on 3.12+ (existing standard).

## Testing Strategy

### Validation Approach

Two phases per bug: first surface a counterexample that fails against the
UNFIXED code (proving the test is real), then apply the fix and confirm the test
passes plus preservation holds. Regression tests live in the v2 unit files
(no live server; mock the version/transport). The library's own test-writing
lesson is honoured: prove each new test can fail before trusting it.

**Test-file placement.** The CI unit suite is a fixed, explicit list:
`test_monitor_types_v2.py`, `test_monitor_params_v2.py`, `test_status_page_v2.py`,
`test_notification_v2.py`, `test_logger.py`, `test_monitor_builder.py`,
`test_status_page_incidents.py`. Recommended mapping:

| Bug | Regression test file | Rationale |
|-----|----------------------|-----------|
| A | **new** `tests/test_delete_id_coercion_v2.py` | spans all seven `delete_*` domains; a dedicated parametrized file is clearest. Mock `get_monitors`/`get_notifications`/… and `_call`. **If created, it MUST be appended to the CI command in `.github/workflows/test.yml`, `AGENTS.md`, and the tech steering.** Lower-churn alternative: fold into `test_monitor_params_v2.py`. |
| B | `tests/test_status_page_v2.py` | `get_status_page` is status-page domain; patch `requests.get` and `_call`, assert `verify` forwarded for both `True`/`False`. |
| C | `tests/test_monitor_params_v2.py` | monitor-domain; set `_event_data[MONITOR_LIST] = None`, mock `_call`/`get_monitor`, assert no `TypeError`. |
| D | `tests/test_monitor_params_v2.py` (or `test_logger.py`) | mock `info()`/`version`; assert nightly/garbage → newest, `2.4.0`/`1.23.2` → correct gate, no raise. |
| E | `tests/test_logger.py` | already patches `socketio.Client`/`connect`; patch `sio.call` to raise `socketio.exceptions.TimeoutError`, assert library `Timeout`. |
| F #69, #57 | `tests/test_notification_v2.py` | provider-metadata assertions (`smtpSecure` type, `notificationIDList` declared default). |
| F #78, #80, #60 | `tests/test_notification_v2.py` (or the new file) | execute the docstring example (assert no `NameError`, key is `monitorID`); assert the auth note text is present. |

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate each bug BEFORE the fix, and
confirm (or refute) the root-cause analysis. If refuted, re-hypothesise.

**Test Plan**: Against the UNFIXED code, drive each `isBugCondition_X` with
mocks and observe the failure.

**Test Cases**:
1. **A**: `delete_monitor("<existing-int-id-as-str>")` with `get_monitors` mocked to return that int id → expect `UptimeKumaException("monitor does not exist")` on unfixed code (will fail-to-delete). Repeat once per site.
2. **B**: construct with `ssl_verify=False`, patch `requests.get`, call `get_status_page` → assert `verify` kwarg present; unfixed code omits it (fails).
3. **C**: force `_event_data[MONITOR_LIST] = None`, call `add_monitor_tag`/`delete_monitor_tag` → `TypeError` on unfixed code.
4. **D**: mock `version` to a nightly string, invoke a gated path → `InvalidVersion` on unfixed code.
5. **E**: patch `sio.call` to raise `socketio.exceptions.TimeoutError`, call `_call` → unfixed code leaks `TimeoutError` (not `Timeout`).
6. **F**: `exec` the class docstring example → `NameError` on `MonitorType`; assert metadata `smtpSecure` type is `"str"` on unfixed code.

**Expected Counterexamples**: type-blind membership failure (A), missing
`verify=` (B), `NoneType` item assignment (C), `InvalidVersion` (D), wrong
exception type (E), `NameError`/wrong-type metadata (F).

### Fix Checking

**Goal**: For all inputs where the bug condition holds, the fixed function
produces the expected behaviour (Properties 1, 3, 5, 7, 9, 11).

**Pseudocode:**
```
FOR EACH bug X IN {A, B, C, D, E, F} DO
  FOR ALL input WHERE isBugCondition_X(input) DO
    result := fixedFunction_X(input)
    ASSERT expectedBehavior_X(result)   // per Property (odd-numbered)
  END FOR
END FOR
```
where `expectedBehavior_X` is: A → entity deleted, no exception; B →
`verify=False` forwarded; C → no exception; D → newest, no raise; E → raises
`Timeout` (an `UptimeKumaException`); F → example runs / metadata type correct.

### Preservation Checking

**Goal**: For all inputs where the bug condition does NOT hold, the fixed
function equals the original (Properties 2, 4, 6, 8, 10, 12).

**Pseudocode:**
```
FOR EACH bug X DO
  FOR ALL input WHERE NOT isBugCondition_X(input) DO
    ASSERT originalFunction_X(input) = fixedFunction_X(input)
  END FOR
END FOR
```

**Testing Approach**: Property-based testing is well suited to the preservation
checks with a bounded input domain — especially Bug A (generate random int/str
ids, present and absent, across sites) and Bug D (generate valid PEP440 strings
and assert the gate result is identical to `parse_version(self.version)`), since
generated cases catch edge cases manual unit tests miss. Observe behaviour on
the UNFIXED code first, then encode it.

**Test Cases**:
1. **A**: int-id delete of an existing entity still succeeds; absent id (str or int) still raises — unchanged from unfixed.
2. **B**: default `ssl_verify=True` forwards `verify=True`; returned status-page dict shape identical.
3. **C**: populated-cache tag add/delete returns and mutates the cache identically.
4. **D**: `2.4.0`, `1.23.2`, `1.17.0`, `2.0` gate identically to the original expression (v1/v2 boundary preserved); `self.version` still returns the raw string.
5. **E**: successful `_call` returns the same `{"ok"}`-unwrapped value; a raised non-timeout error propagates unchanged.
6. **F**: representative runtime call keeps its signature/return; effective `notificationIDList` payload and accepted `smtpSecure` values unchanged.

### Unit Tests

- Bug A: one delete test per site by `str` and `int` id, plus an absent id still raising (14 + 7 assertions in spirit; parametrized).
- Bug B: `verify` forwarded as both `True` and `False`; return shape preserved.
- Bug C: `None`-cache add/delete succeed; populated-cache path unchanged.
- Bug D: nightly, garbage, `2.4.0`, `1.23.2` each yield a usable gate result; `version` property still raw.
- Bug E: timeout → `Timeout`; success → same result; non-timeout error → unchanged.
- Bug F: docstring example executes; `smtpSecure` type is `"bool"`; `notificationIDList` declared default is `[]`; auth note present.

### Property-Based Tests

- Bug A: generate random ids (int and numeric-string, present and absent) over the seven sites; assert deletes for existing, raises for absent, regardless of caller type.
- Bug D: generate valid PEP440 strings; assert `_parsed_version()` gate equals the original `parse_version(self.version)` gate; generate non-PEP440 strings; assert never raises and compares as newest.
- Bug B/C/E: generate the non-bug side of the domain (trusted certs, populated caches, successful/non-timeout calls) and assert `F' = F`.

### Integration Tests

Integration coverage stays out of CI (the inherited suite wipes live data). Any
live confirmation uses the manual `live_test_*` scripts against the disposable
instance in `tests/.env`, dry-run first — never bare `pytest tests/`. Optional
manual checks: delete-by-string-id round trip, `get_status_page` against a
self-signed cert with `ssl_verify=False`, and a tag add on a fresh session
(empty cache).
