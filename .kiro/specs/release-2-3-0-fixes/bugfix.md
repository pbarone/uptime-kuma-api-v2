# Bugfix Requirements Document

## Introduction

This is the "2.3.0 batch" of fixes for the `uptime-kuma-api2` Python library
(import package `uptime_kuma_api`). It bundles five confirmed library defects
plus a docs/metadata sweep, all documented in `UPSTREAM_TRIAGE.md` section 5.
No new public API surface is added; the goal is to correct defective behavior
while leaving every existing v1.x and v2.x contract intact.

Each defect is treated as a **distinct bug condition** with both fix checking
(the bug is corrected for the inputs that trigger it) and preservation checking
(behavior is unchanged for every input that does not trigger it). Because
backward compatibility with Uptime Kuma v1.x is sacred and public method
signatures and return shapes are a contract, every clause below is written so
that the corrected behavior is additive or corrective, never breaking.

The six items in scope:

- **Bug A (#91, PR #92)** — string/int id mismatch in all seven `delete_*` guards.
- **Bug B (#65, PR #81)** — `ssl_verify` ignored by `get_status_page`.
- **Bug C (#68)** — monitor-list cache write crash on `None` cache in tag ops.
- **Bug D (#74)** — non-PEP440 server versions crash every version gate.
- **Bug E (#44)** — socket.io timeouts leak the wrong exception type.
- **Bug F (docs/metadata sweep: #78, #80, #60, #69, #57)** — documentation and
  provider-metadata corrections with no runtime behavior change.

Explicitly out of scope (must NOT be implemented): PR #84's required-args
change, PR #94 (superseded), PR #86's `get_monitors` refactor, and PR #88/#87
code.

## Bug Analysis

### Current Behavior (Defect)

**Bug A — string/int id guard (#91)**

1.1 WHEN a `delete_*` method is called with a string id whose numeric value
matches an existing entity (e.g. `delete_monitor("371")` where monitor 371
exists) THEN the system raises `UptimeKumaException` "... does not exist"
because the guard compares the string against integer ids via
`if id_ not in [i["id"] for i in ...]`.

1.2 WHEN the string/int mismatch occurs at any of the seven affected sites
(monitor, notification, proxy, tag, docker host, maintenance, api key) THEN the
system fails the membership check identically at each site and the delete is
never sent to the server.

**Bug B — `ssl_verify` ignored by `get_status_page` (#65)**

1.3 WHEN the API is constructed with `ssl_verify=False` THEN the system passes
`ssl_verify` only to `socketio.Client` and never stores it on the instance, so
the value is lost for later HTTP calls.

1.4 WHEN `get_status_page` performs its `requests.get` call against a server
with a self-signed certificate THEN the system omits any `verify=` argument and
the request fails TLS verification even though the caller requested
`ssl_verify=False`.

**Bug C — monitor-list cache write crash (#68)**

1.5 WHEN `add_monitor_tag` or `delete_monitor_tag` is called while the cached
monitor list `_event_data[MONITOR_LIST]` is `None` THEN the system attempts an
item assignment into `None` and raises `TypeError: 'NoneType' object does not
support item assignment`.

**Bug D — non-PEP440 server versions crash version gates (#74)**

1.6 WHEN the connected server reports a non-PEP440 version string (e.g. a
nightly build like `2.0.0-dev-nightly-...`) THEN the system feeds the raw
string into `packaging.version.parse` and raises `InvalidVersion`.

1.7 WHEN any version-gated code path executes against such a server THEN the
system fails at the gate (the defect surfaces at ~10 parse sites), breaking
otherwise-supported operations.

**Bug E — socket.io timeout leaks wrong exception type (#44)**

1.8 WHEN a socket.io call in `_call` times out THEN the system leaks
`socketio.exceptions.TimeoutError` to the caller instead of the library's own
`Timeout` exception, so callers catching `UptimeKumaException` / `Timeout` do
not catch it.

**Bug F — docs and metadata defects (#78, #80, #60, #69, #57)**

1.9 WHEN a user follows the README context-manager example or the `api.py`
docstring examples that reference `MonitorType` THEN the example omits the
`MonitorType` import and fails with `NameError` (#78).

1.10 WHEN a user follows the `api.py` example that references the heartbeat
parameter THEN it uses the incorrect casing `monitorId` instead of `monitorID`
(#80; README was already corrected in 2.2.1).

1.11 WHEN a user tries to authenticate this socket.io API using the Uptime Kuma
UI "API key" THEN the documentation does not state that this is impossible
(UI API keys are `/metrics`-only), leaving users to discover it by failure
(#60/#73).

1.12 WHEN provider metadata for SMTP is consumed (required-arg check, docstring
generation, downstream Ansible collection) THEN `smtpSecure` is declared as
`type="str"` although upstream `SMTP.vue` treats it as a boolean (#69).

1.13 WHEN provider/monitor metadata declares the `notificationIDList` default
THEN it uses `{}` (a dict) rather than `[]`, misrepresenting the declared type
(#57).

### Expected Behavior (Correct)

**Bug A — string/int id guard (#91)**

2.1 WHEN a `delete_*` method is called with a string id whose numeric value
matches an existing entity THEN the system SHALL coerce the id for the
membership check so the entity is found, coerce the value sent to the server,
and successfully delete the entity.

2.2 WHEN a `delete_*` method is called with an integer or string id at any of
the seven sites (monitor, notification, proxy, tag, docker host, maintenance,
api key) THEN the system SHALL resolve the entity identically regardless of the
caller-supplied type.

2.3 WHEN a `delete_*` method is called with an id (string or int) that does not
correspond to any existing entity THEN the system SHALL still raise
`UptimeKumaException` "... does not exist".

**Bug B — `ssl_verify` ignored by `get_status_page` (#65)**

2.4 WHEN the API is constructed THEN the system SHALL store `ssl_verify` on the
instance in `__init__` so it is available to HTTP calls.

2.5 WHEN `get_status_page` (and any other `requests` HTTP call that requires it)
issues its request THEN the system SHALL pass `verify=self.ssl_verify`, so a
`ssl_verify=False` caller can fetch a status page from a server with a
self-signed certificate.

**Bug C — monitor-list cache write crash (#68)**

2.6 WHEN `add_monitor_tag` or `delete_monitor_tag` is called while the cached
monitor list is `None` THEN the system SHALL initialise the cache first (mirror
the pattern used in `add_status_page`) and complete the call without raising.

**Bug D — non-PEP440 server versions crash version gates (#74)**

2.7 WHEN the connected server reports a non-PEP440 / unparseable version string
THEN the system SHALL normalise it behind a single choke point (the `version`
property) and treat an unparseable version as newest, never raising
`InvalidVersion`.

2.8 WHEN the server reports a nightly string, `2.4.0`, `1.23.2`, or a garbage
string THEN the system SHALL produce a usable gate result for each, so
version-gated code paths execute correctly.

**Bug E — socket.io timeout leaks wrong exception type (#44)**

2.9 WHEN a socket.io call in `_call` times out THEN the system SHALL catch
`socketio.exceptions.TimeoutError` and re-raise the library's own `Timeout`
exception (which subclasses `UptimeKumaException`), so existing handlers keep
working.

**Bug F — docs and metadata corrections (#78, #80, #60, #69, #57)**

2.10 WHEN a user follows the README context-manager example or the `api.py`
docstring examples referencing `MonitorType` THEN the examples SHALL include the
`MonitorType` import so they run without `NameError` (#78).

2.11 WHEN a user follows the `api.py` heartbeat example THEN it SHALL use
`monitorID` with correct casing (#80).

2.12 WHEN a user reads the authentication documentation THEN it SHALL state that
the UI "API key" cannot authenticate this socket.io API (#60/#73).

2.13 WHEN SMTP provider metadata is consumed THEN `smtpSecure` SHALL be declared
as `type="bool"` (verified against upstream `SMTP.vue`) (#69).

2.14 WHEN `notificationIDList` metadata default is declared THEN it SHALL be `[]`
rather than `{}`, correcting the declared type without changing behavior (#57).

### Unchanged Behavior (Regression Prevention)

**Bug A — string/int id guard (#91)**

3.1 WHEN a `delete_*` method is called with an integer id for an existing entity
THEN the system SHALL CONTINUE TO delete it successfully as before.

3.2 WHEN a `delete_*` method is called with a genuinely absent id THEN the
system SHALL CONTINUE TO raise the existing "... does not exist" exception and
send no delete to the server.

**Bug B — `ssl_verify` ignored by `get_status_page` (#65)**

3.3 WHEN the API is constructed with the default `ssl_verify=True` THEN the
system SHALL CONTINUE TO verify SSL certificates for both the socket.io
connection and HTTP calls.

3.4 WHEN `get_status_page` is used against a normally-trusted server THEN the
system SHALL CONTINUE TO return the same status page structure and fields as
before.

**Bug C — monitor-list cache write crash (#68)**

3.5 WHEN `add_monitor_tag` or `delete_monitor_tag` is called while the monitor
list cache is already populated THEN the system SHALL CONTINUE TO update the
cache and return the same result as before.

**Bug D — non-PEP440 server versions crash version gates (#74)**

3.6 WHEN the server reports a valid PEP440 version (e.g. `2.4.0`, `1.23.2`)
THEN the system SHALL CONTINUE TO gate v1.x versus v2.x behavior exactly as
before, keeping v1.17+ connections correct.

**Bug E — socket.io timeout leaks wrong exception type (#44)**

3.7 WHEN a socket.io call in `_call` succeeds THEN the system SHALL CONTINUE TO
return the same result (including the existing `{"ok": ...}` unwrapping) as
before.

3.8 WHEN a call raises a non-timeout error THEN the system SHALL CONTINUE TO
surface it unchanged (only `TimeoutError` is translated).

**Bug F — docs and metadata corrections (#78, #80, #60, #69, #57)**

3.9 WHEN any public method is called at runtime THEN the system SHALL CONTINUE
TO expose the same method signatures and return shapes — the docs/metadata sweep
is behaviour-neutral.

3.10 WHEN a monitor is added without specifying notifications THEN the system
SHALL CONTINUE TO send the same effective `notificationIDList` payload as before
(the `{}`→`[]` change corrects the declared type only, not the behavior).

3.11 WHEN an SMTP notification is created THEN the system SHALL CONTINUE TO
accept and forward the same `smtpSecure` values as before (the metadata type
correction changes validation/docs classification, not accepted values).

---

## Bug Conditions and Properties

The batch contains six independent bug conditions. `F` is the original
(unfixed) function; `F'` is the fixed function. For every bug, preservation is
the same shape: for all inputs that do not meet the bug condition, `F(X) = F'(X)`.

### Bug A — string/int id guard (#91)

```pascal
FUNCTION isBugCondition_A(X)
  INPUT: X = (site, id_) where site is one of the seven delete_* methods
  OUTPUT: boolean

  // The entity exists, but the caller-supplied id type differs from the
  // stored id type such that raw membership testing fails.
  RETURN entityExists(site, coerce(id_)) AND (id_ NOT IN storedIds(site))
END FUNCTION
```

```pascal
// Property: Fix Checking - id type coercion
FOR ALL X WHERE isBugCondition_A(X) DO
  result ← delete'(X.site, X.id_)
  ASSERT deletionSentToServer(result) AND no_exception(result)
END FOR

// Property: Preservation - absent ids still raise, int ids still work
FOR ALL X WHERE NOT isBugCondition_A(X) DO
  ASSERT delete(X) = delete'(X)
END FOR
```

### Bug B — `ssl_verify` in `get_status_page` (#65)

```pascal
FUNCTION isBugCondition_B(X)
  INPUT: X = api instance with ssl_verify flag
  OUTPUT: boolean

  // A status-page HTTP fetch occurs while ssl_verify was requested False.
  RETURN X.performsRequestsGet AND X.ssl_verify = False
END FUNCTION
```

```pascal
// Property: Fix Checking - verify forwarded
FOR ALL X WHERE isBugCondition_B(X) DO
  ASSERT requestsGetCalledWith(verify = False)
END FOR

// Property: Preservation - default True still verifies, same return shape
FOR ALL X WHERE NOT isBugCondition_B(X) DO
  ASSERT requestsGetCalledWith(verify = True) AND statusPageShape(F'(X)) = statusPageShape(F(X))
END FOR
```

### Bug C — monitor-list cache write (#68)

```pascal
FUNCTION isBugCondition_C(X)
  INPUT: X = (op, cacheState) where op in {add_monitor_tag, delete_monitor_tag}
  OUTPUT: boolean

  RETURN cacheState[MONITOR_LIST] = None
END FUNCTION
```

```pascal
// Property: Fix Checking - no crash when cache is None
FOR ALL X WHERE isBugCondition_C(X) DO
  result ← op'(X)
  ASSERT no_exception(result)
END FOR

// Property: Preservation - populated cache behaves identically
FOR ALL X WHERE NOT isBugCondition_C(X) DO
  ASSERT op(X) = op'(X)
END FOR
```

### Bug D — non-PEP440 version (#74)

```pascal
FUNCTION isBugCondition_D(X)
  INPUT: X = raw server version string
  OUTPUT: boolean

  RETURN NOT isPep440Parseable(X)
END FUNCTION
```

```pascal
// Property: Fix Checking - unparseable treated as newest, never raises
FOR ALL X WHERE isBugCondition_D(X) DO
  result ← versionGate'(X)
  ASSERT no_exception(result) AND result = TREAT_AS_NEWEST
END FOR

// Property: Preservation - valid versions gate exactly as before
FOR ALL X WHERE NOT isBugCondition_D(X) DO
  ASSERT versionGate(X) = versionGate'(X)
END FOR
```

### Bug E — timeout translation (#44)

```pascal
FUNCTION isBugCondition_E(X)
  INPUT: X = a _call invocation
  OUTPUT: boolean

  RETURN raises(X, socketio.exceptions.TimeoutError)
END FUNCTION
```

```pascal
// Property: Fix Checking - re-raised as library Timeout
FOR ALL X WHERE isBugCondition_E(X) DO
  ASSERT raises(F'(X), Timeout) AND isinstance(Timeout, UptimeKumaException)
END FOR

// Property: Preservation - success and non-timeout errors unchanged
FOR ALL X WHERE NOT isBugCondition_E(X) DO
  ASSERT F(X) = F'(X)
END FOR
```

### Bug F — docs/metadata sweep (#78, #80, #60, #69, #57)

```pascal
FUNCTION isBugCondition_F(X)
  INPUT: X = a documentation example or a metadata declaration
  OUTPUT: boolean

  // Static defect: example fails to run, or metadata declares the wrong type.
  RETURN exampleFailsToRun(X) OR metadataTypeIncorrect(X)
END FUNCTION
```

```pascal
// Property: Fix Checking - examples run, metadata types correct
FOR ALL X WHERE isBugCondition_F(X) DO
  ASSERT exampleRuns(X) OR metadataTypeCorrect(X)
END FOR

// Property: Preservation - runtime behavior/return shapes unchanged
FOR ALL X WHERE NOT isBugCondition_F(X) DO
  ASSERT runtimeBehavior(F'(X)) = runtimeBehavior(F(X))
END FOR
```
