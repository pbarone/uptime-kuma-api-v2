# Bugfix Requirements Document

## Introduction

On Uptime Kuma 2.x the library's cached monitor list goes stale after every monitor
mutation. Uptime Kuma 2.x replaced the post-mutation full-list `monitorList` broadcast
with two delta events — `updateMonitorIntoList` (one or more `{id: monitor}` entries)
and `deleteMonitorFromList` (an id alone) — and the library registers no handlers for
either, so those packets are dropped silently. `get_monitors()` reads only the cached
`monitorList`, never the `getMonitorList` RPC, so after any mutation it returns
session-stale data for the rest of the session.

The user-visible symptom is a `delete_monitor(id)` call raising
`UptimeKumaException: monitor does not exist` for a monitor created moments earlier in
the same session, with the delete never reaching the server: the guard builds its id
list from `get_monitors()` and rejects before `_call('deleteMonitor', ...)` is reached.
The failure reproduces with an `int` id, which is what proves it is distinct from the
already-fixed string-id coercion defect (#91).

Two guards read the cache before deciding, not one: `delete_monitor` and
`delete_monitor_tag`. `wait_for_event`, which four monitor methods wrap themselves in,
never resets the cache entry before waiting, so once login has populated the entry the
wait returns immediately — on 2.x and on v1.x alike. On v1.x that latent race is masked
by the full-list broadcast arriving during the unconditional `time.sleep(wait_events)`
inside `_get_event_data`.

There is no upstream issue number; the defect was found during 2.3.0 live verification
against server 2.4.0 and affects the original upstream library identically. The complete
sourced diagnosis, with server-source citations, instrumented evidence and a
reproduction recipe, is in `UPSTREAM_TRIAGE.md` section 7.

**Scope of the fix.** Cache coherence after every monitor mutation on 2.x (add, edit,
delete, pause, resume, and the monitor-tag operations); the two cache-reading guards
deciding correctly; regression tests in the v2 unit suite, each proven to fail against
the unfixed code first; a written v1.x compatibility argument; removal of the temporary
scaffolding in `tests/live_test_delete_id.py`; a `CHANGELOG.md` entry.

**Explicitly out of scope.** The other six `delete_*` guards — notifications, proxies,
docker hosts, API keys, tags and status pages — are unaffected and must not be touched:
2.x still broadcasts a full list for each of those resources on mutation
(`server/client.js` retains `sendNotificationList`, `sendProxyList`, `sendAPIKeyList`
and `sendDockerHostList`, and has no `sendMonitorList` at all). Also out of scope is
anything touching the #91 string-id coercion, which is already present and correct.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a monitor is added on a 2.x server THEN the system leaves the cached monitor list unchanged, so `get_monitors()` omits the id that `add_monitor` just returned, because the server's `updateMonitorIntoList` event has no handler

1.2 WHEN `delete_monitor` is called with a valid id for a monitor created earlier in the same session on a 2.x server THEN the system raises `UptimeKumaException: monitor does not exist` and never sends `deleteMonitor` to the server, because the guard builds its id list from the stale cache

1.3 WHEN a monitor is deleted on a 2.x server THEN the system leaves the deleted monitor in the cached list, so `get_monitors()` still reports it as present, because the server's `deleteMonitorFromList` event has no handler

1.4 WHEN a monitor is edited on a 2.x server THEN the system continues to serve the pre-edit field values from `get_monitors()` for the rest of the session

1.5 WHEN a monitor is paused or resumed on a 2.x server THEN the system continues to serve the previous `active` value from `get_monitors()`, and `pause_monitor` / `resume_monitor` do not even attempt to wait for a refresh

1.6 WHEN `delete_monitor_tag` is called on a 2.x server after any monitor mutation THEN the system may raise `UptimeKumaException: monitor tag does not exist` for a tag that does exist, because that guard also builds its existence check from `get_monitors()`

1.7 WHEN `wait_for_event(Event.MONITOR_LIST)` is entered after login has already populated the cache entry THEN the system returns immediately without waiting for any refresh, on both 2.x and v1.x, because the loop only waits while the entry is `None` and the entry is never reset — so the wraps in `add_monitor`, `edit_monitor`, `delete_monitor` and `delete_monitor_tag` are all no-ops, and the helper's docstring comment does not say so

### Expected Behavior (Correct)

2.1 WHEN the server emits `updateMonitorIntoList` THEN the system SHALL merge each `{id: monitor}` entry from the payload into the cached monitor list, so a monitor added or changed on 2.x is visible to `get_monitors()` without a caller-side workaround

2.2 WHEN `delete_monitor` is called with a valid id THEN the system SHALL refresh the monitor list deterministically before evaluating its existence guard, and SHALL send `deleteMonitor` to the server, so correctness does not depend on event or ack ordering

2.3 WHEN the server emits `deleteMonitorFromList` THEN the system SHALL remove the identified monitor from the cached list, so `get_monitors()` no longer reports a deleted monitor as present

2.4 WHEN a monitor is edited on a 2.x server THEN the system SHALL serve the post-edit field values from `get_monitors()`

2.5 WHEN a monitor is paused or resumed on a 2.x server THEN the system SHALL serve the post-mutation `active` value from `get_monitors()`

2.6 WHEN `delete_monitor_tag` is called THEN the system SHALL refresh the monitor list deterministically before evaluating its existence guard, so an existing monitor tag is not rejected

2.7 WHEN a maintainer or caller reads `wait_for_event` THEN the system SHALL document in place that it waits only for the first event of that type and is a no-op once the entry is populated, so the helper is no longer silently misleading; its signature and runtime semantics SHALL NOT change

2.8 WHEN `tests/live_test_delete_id.py` is run against a disposable 2.x instance with all temporary scaffolding removed THEN the script SHALL pass — specifically with the three `api._call("getMonitorList")` workarounds (Step 2 pre-delete, Step 2 post-delete read, cleanup int-id fallback), the Step 2 staleness probe, the `known_issue()` helper and its reporting block, and the `TEMPORARY SCAFFOLDING` section of the module docstring all deleted

2.9 WHEN the fix is delivered THEN it SHALL ship with regression tests in the v2 unit suite, each demonstrated to fail against the unfixed code before the fix lands, and with a `CHANGELOG.md` entry

2.10 WHEN the fix is delivered THEN the v1.x compatibility argument SHALL be written down explicitly: the delta-event handlers are inert on v1.x because v1.x never emits those events, and the guard refresh is unconditional because `getMonitorList` exists in both 1.23.X and 2.x

### Unchanged Behavior (Regression Prevention)

3.1 WHEN connected to a v1.x server THEN the system SHALL CONTINUE TO populate the cached monitor list from the full `monitorList` broadcast that v1.x sends after every mutation, with the new delta handlers inert because v1.x never emits those events

3.2 WHEN connected to a v1.x server THEN `add_monitor`, `edit_monitor`, `delete_monitor`, `pause_monitor`, `resume_monitor` and the monitor-tag operations SHALL CONTINUE TO work with no version gating introduced by this fix, and no new `self.version` lookup on these paths (a version check routes through `info()` → `_get_event_data`, whose 0.2s `wait_events` sleep costs more than the 2-6ms `getMonitorList` round trip it would guard)

3.3 WHEN `delete_monitor` is called with an id that genuinely does not exist on the server THEN the system SHALL CONTINUE TO raise `UptimeKumaException` with the message `monitor does not exist` and SHALL NOT send a delete

3.4 WHEN `delete_monitor` is called with a string id, numeric (`"7"`) or non-numeric (`"not-an-id"`) THEN the system SHALL CONTINUE TO behave exactly as the already-shipped #91 coercion fix specifies, raising the library's own `UptimeKumaException` rather than leaking a `ValueError`

3.5 WHEN the server has zero monitors, so the cached monitor list is the `{}` sentinel THEN `_get_event_data` SHALL CONTINUE TO short-circuit and return `[]` for `avgPing`, `uptime`, `heartbeatList`, `importantHeartbeatList`, `certInfo` and `heartbeat` instead of blocking until the timeout — no part of this fix may clear the cache to `None` or `{}` mid-session in a way that collides with that sentinel

3.6 WHEN a notification, proxy, docker host, API key, tag or status page is deleted THEN those six `delete_*` guards SHALL CONTINUE TO behave exactly as they do today, unmodified, since 2.x still broadcasts a full list for each of those resources

3.7 WHEN `add_monitor_tag` or `delete_monitor_tag` completes THEN the system SHALL CONTINUE TO patch the target monitor's cache entry under its string key, as both methods already do

3.8 WHEN a caller uses the library's public surface THEN the system SHALL NOT expose any new public method, parameter, class or export as part of this fix

3.9 WHEN `get_monitors()` or `get_monitor(id)` returns THEN the system SHALL CONTINUE TO return the same shape as today — a list of monitor dicts and a single monitor dict respectively, with the same parsing of `type`, `status`, `authMethod` and `notificationIDList` applied

### Bug Condition and Properties

The defect has two distinct triggers that the fix must both close. The first is the
missing delta handlers, which is 2.x-only. The second is the guards trusting a cache
read, which is latent on v1.x and load-bearing on 2.x.

```pascal
FUNCTION isCacheStaleCondition(X)
  INPUT: X = (server_version, operation)
  OUTPUT: boolean

  // 2.x answers a monitor mutation with a delta event the library drops
  RETURN server_version >= 2.0
     AND X.operation IN {add, edit, delete, pause, resume,
                         addMonitorTag, editMonitorTag, deleteMonitorTag}
END FUNCTION
```

```pascal
FUNCTION isStaleGuardCondition(X)
  INPUT: X = (guard, cache_state, server_state)
  OUTPUT: boolean

  // a guard decides from the cache, and the cache disagrees with the server
  RETURN X.guard IN {delete_monitor, delete_monitor_tag}
     AND X.cache_state <> X.server_state
END FUNCTION
```

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type SessionOperation
  OUTPUT: boolean

  RETURN isCacheStaleCondition(X) OR isStaleGuardCondition(X)
END FUNCTION
```

**Property: Fix Checking — cache coherence.** For every monitor mutation on 2.x, the
cached list read back afterwards must agree with the server.

```pascal
// Property: Fix Checking - cache coherence after mutation
FOR ALL X WHERE isCacheStaleCondition(X) DO
  apply(X.operation)
  ASSERT get_monitors'() = server_monitor_list()
END FOR
```

**Property: Fix Checking — guards decide on fresh data.** A guard that reads the cache
must never reject an id the server actually has, and must still reject one it does not.

```pascal
// Property: Fix Checking - guard correctness
FOR ALL X WHERE isStaleGuardCondition(X) DO
  result <- guard'(X)
  ASSERT (X.id IN server_state) IMPLIES (result = accepted AND request_sent(X))
  ASSERT (X.id NOT IN server_state) IMPLIES
         (result = UptimeKumaException("... does not exist") AND NOT request_sent(X))
END FOR
```

**Property: Preservation Checking.** For every input that does not meet the bug
condition — every v1.x session, every non-monitor resource, the zero-monitor sentinel
path, the #91 string-id paths, and `wait_for_event`'s observable semantics — the fixed
library must behave identically to the current one.

```pascal
// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT F(X) = F'(X)
END FOR
```

Here `F` is the library as it exists before the fix and `F'` the library after it.
