# Monitor List Cache Staleness Bugfix Design

## Overview

Uptime Kuma 2.x answers a monitor mutation with one of two *delta* events —
`updateMonitorIntoList` (`{id: monitor}`, one or more entries) or
`deleteMonitorFromList` (the id alone) — where 1.23.X sent a full `monitorList`
broadcast. The library registers no handler for either, so those packets are
dropped and the cached monitor list is session-stale from the first mutation
onwards. `get_monitors()` reads only that cache, and two guards decide from
`get_monitors()`, so `delete_monitor` rejects an id the server demonstrably has.

The fix has two halves, and both are needed:

1. **Delta-event handlers.** Register `updateMonitorIntoList` and
   `deleteMonitorFromList` handlers that merge into / remove from the cached
   `monitorList` entry. This is what the real frontend does, and it is the only
   mechanism that can cover mutations the library did not initiate itself
   (another client, the web UI) and the server's per-child cascade events on a
   group delete.
2. **A deterministic refresh in the two cache-reading guards.** `delete_monitor`
   and `delete_monitor_tag` call a new private `_refresh_monitor_list()` before
   evaluating their existence check, so the decision never depends on an event
   having already been delivered.

Neither half is version-gated. The handlers are inert on v1.x because v1.x never
emits those events; the refresh is unconditional because `getMonitorList` exists
in 1.23.X and 2.x alike, and a `self.version` check would route through `info()`
→ `_get_event_data` and its 0.2 s `wait_events` sleep — an order of magnitude
more expensive than the 2-6 ms RPC it would guard. `wait_for_event`'s runtime
semantics are unchanged; its first-event-only behaviour is documented in place.
No new public method, parameter or export.

## Glossary

- **Bug_Condition (C)**: a monitor mutation on a 2.x server (the library drops
  the delta event), or a cache-reading guard whose cached view disagrees with the
  server. Formalised as `isCacheStaleCondition` / `isStaleGuardCondition` in
  `bugfix.md`.
- **Property (P)**: after any monitor mutation, `get_monitors()` agrees with the
  server; and a guard accepts every id the server has while still rejecting every
  id it does not.
- **Preservation**: every v1.x session, the six non-monitor `delete_*` guards, the
  `{}` zero-monitor sentinel, the #91 string-id contract, and `wait_for_event`'s
  observable semantics behave exactly as they do today.
- **Delta event**: `updateMonitorIntoList` / `deleteMonitorFromList` — 2.x's
  per-monitor replacements for the full `monitorList` broadcast.
- **The cache**: `self._event_data[Event.MONITOR_LIST]`, a dict keyed by
  **stringified** monitor id (`{"1": {...}}`), or `None` before the first
  `monitorList` arrives, or `{}` when the server has zero monitors.
- **`_event_data`**: the event-payload store, initialised in `__init__`
  (api.py:489) and keyed by `Event` members. It backs `wait_for_event` and
  `_get_event_data`.
- **`get_monitors`** (api.py:1327): reads the cache via `_get_event_data`, never
  the `getMonitorList` RPC. Its `# TODO: replace with getMonitorList?` comment is
  the defect, pre-annotated by the original author.
- **The two guards**: `delete_monitor` (api.py:1578) and `delete_monitor_tag`
  (api.py:1798) — the only monitor methods that read the cache to decide whether
  to send a request at all.
- **`{}` sentinel**: `_get_event_data` (api.py:555) treats an empty cached monitor
  list as "the server has no monitors" and returns `[]` for the six
  monitor-scoped events rather than blocking until timeout.

## Bug Details

### Bug Condition

The bug manifests on two distinct triggers. Either the server emits a delta event
the library has no handler for, leaving the cache behind the server for the rest
of the session; or a guard reads that cache and rejects a request for an entity
the server actually has.

**Formal Specification:**

```
FUNCTION isBugCondition(input)
  INPUT: input = (server_version, operation, guard, cache_state, server_state)
  OUTPUT: boolean

  cache_stale := input.server_version >= 2.0
                 AND input.operation IN {add, edit, delete, pause, resume,
                                         addMonitorTag, editMonitorTag,
                                         deleteMonitorTag}

  stale_guard := input.guard IN {delete_monitor, delete_monitor_tag}
                 AND input.cache_state <> input.server_state

  RETURN cache_stale OR stale_guard
END FUNCTION
```

### Examples

- `add_monitor(...)` returns `monitorID: 2`; `get_monitors()` immediately after
  returns ids `[1]` — expected `[1, 2]`. Instrumented: exactly **one**
  `monitorList` event in the whole session, received at login.
- `delete_monitor(2)` for that monitor raises
  `UptimeKumaException: monitor does not exist` and never sends `deleteMonitor`.
  Reproduces with an **int** id, which is what proves it is not #91.
- `delete_monitor(2)` succeeds; `get_monitors()` still lists monitor 2 as
  present — expected absent.
- `edit_monitor(1, interval=20)` succeeds; `get_monitors()` keeps returning
  `interval: 60` for the rest of the session.
- `pause_monitor(1)` succeeds; `get_monitors()` keeps returning `active: True`.
- `delete_monitor_tag(tag_id=1, monitor_id=1, value="x")` raises
  `monitor tag does not exist` for a tag that does exist, because its guard also
  builds from `get_monitors()`.
- Edge case: `api._call("getMonitorList")` before any of the above makes all of
  them behave correctly — the confirmation that this is a cache defect, not a
  server one.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**

- v1.x sessions: the full `monitorList` broadcast after every mutation keeps
  populating the cache exactly as today, with the delta handlers never firing.
- No `self.version` / `_parsed_version()` lookup is introduced on any monitor
  path, so no monitor method gains an `info()` round trip.
- `delete_monitor` with a genuinely absent id still raises
  `UptimeKumaException("monitor does not exist")` and still sends nothing.
- `delete_monitor` with a string id — `"7"` or `"not-an-id"` — behaves exactly as
  the shipped #91 coercion specifies, raising the library's own exception rather
  than leaking `ValueError`.
- The `{}` zero-monitor sentinel keeps short-circuiting `avgPing`, `uptime`,
  `heartbeatList`, `importantHeartbeatList`, `certInfo` and `heartbeat` to `[]`.
- The other six `delete_*` guards (notifications, proxies, docker hosts, API
  keys, tags, status pages) are not touched: 2.x still broadcasts a full list for
  each of those resources.
- `add_monitor_tag` / `delete_monitor_tag` keep patching the target monitor's
  cache entry under its string key.
- `get_monitors()` / `get_monitor(id)` return the same shapes, with the same
  `type` / `status` / `authMethod` / `notificationIDList` parsing.
- `wait_for_event`'s signature and runtime behaviour are byte-for-byte unchanged.
- No new public method, parameter, class or export.

**Scope:**

Everything outside a 2.x monitor mutation and the two monitor guards must be
completely unaffected. Specifically:

- every v1.x session, on every method;
- every non-monitor resource, including its `delete_*` guard;
- the zero-monitor sentinel path;
- the #91 string-id paths;
- `wait_for_event` as observed by any caller.

The actual expected correct behaviour is in **Correctness Properties** below.

## Hypothesized Root Cause

The root cause is not hypothesised — it was read off the upstream server source
and confirmed by instrumented evidence (`UPSTREAM_TRIAGE.md` section 7). What
follows is therefore a confirmed causal chain, with the residual uncertainty
called out where it exists.

1. **2.x replaced the full-list broadcast with delta events (confirmed).**
   `server/uptime-kuma-server.js` (master) defines `sendUpdateMonitorIntoList` →
   `updateMonitorIntoList` and `sendDeleteMonitorFromList` →
   `deleteMonitorFromList`; `server/client.js` has no `sendMonitorList` at all,
   while `sendNotificationList`, `sendProxyList`, `sendAPIKeyList` and
   `sendDockerHostList` are all still present. In 1.23.X, `add`, `editMonitor`,
   `pauseMonitor`, `resumeMonitor` **and** `deleteMonitor` every one call
   `sendMonitorList`. Only `getMonitorList` and `afterLogin` still do on master.

2. **The library has no handler for either delta event (confirmed).**
   `event.py` defines `MONITOR_LIST` only, and `__init__` registers handlers for
   the 17 events it knows (api.py:506-524). python-socketio silently drops an
   event with no registered handler, so nothing in the library ever sees them.

3. **`get_monitors()` reads only the cache (confirmed).** api.py:1412 is
   `list(self._get_event_data(Event.MONITOR_LIST).values())`, so a stale cache is
   a stale return value with no server round trip to correct it.

4. **The guards trust that cache read (confirmed).** `delete_monitor` builds
   `ids = [i["id"] for i in self.get_monitors()]`; `delete_monitor_tag` builds its
   tag triples from `self.get_monitors()`. Both raise before `_call`.

5. **`wait_for_event` cannot rescue any of this (confirmed).** It loops
   `while self._event_data[event] is None` and never resets the entry, so once
   login has populated it the four monitor wraps (api.py:1578, 1711, 1738, 1798)
   return instantly. On v1.x this latent no-op is masked by the post-mutation
   full-list broadcast landing during `_get_event_data`'s unconditional 0.2 s
   `wait_events` sleep.

**Delivery ordering — the part that needed verifying, because the fix's
determinism argument rests on it.** Read off `server/server.js` (master):

| Server handler | Order on the wire |
|---|---|
| `add`, `editMonitor`, `pauseMonitor`, `resumeMonitor`, `addMonitorTag`, `editMonitorTag` | `await sendUpdateMonitorIntoList(...)` **then** `callback(...)` — delta precedes the ack |
| `getMonitorList` | `await sendMonitorList(socket)` **then** `callback({ok:true})` — full list precedes the ack |
| `deleteMonitor` | `callback(...)` **then** `await sendDeleteMonitorFromList(...)` — delta *follows* the ack, and emits one event per child on a group cascade |

And on the client side, `socketio.Client` (sync) dispatches **synchronously** on
the single engine.io read-loop thread: `_handle_eio_message` calls `_handle_event`
→ `_trigger_event` → the handler inline (there is no `async_handlers` option and
no `start_background_task` on this path, verified in the pinned
`socketio/client.py`), and `_handle_ack` — which sets the `threading.Event` that
`sio.call` waits on — is dispatched from the same loop, in packet arrival order.

So for `getMonitorList`, the `monitorList` packet is processed, and
`_event_monitor_list` has finished running, **before** the ack that lets `_call`
return. That is what makes `_refresh_monitor_list()` deterministic rather than
hopeful, and it is why the same reasoning does *not* extend to `deleteMonitor`:
there the server acks first, so the delete's own delta lands a few milliseconds
after `_call` returns and is picked up during the next read's 0.2 s `wait_events`
window (see the *Post-delete read* note under Fix Implementation).

## Correctness Properties

Property 1: Bug Condition - Delta events keep the cached monitor list coherent

_For any_ monitor mutation on a 2.x server (isBugCondition returns true via
`isCacheStaleCondition`), the fixed library SHALL apply the server's delta event
to the cached monitor list — merging each `{id: monitor}` entry of
`updateMonitorIntoList` under its stringified id, and removing the id carried by
`deleteMonitorFromList` — so that `get_monitors()` reports the added monitor, the
post-edit field values, the post-mutation `active` flag, and the absence of a
deleted monitor.

**Validates: Requirements 2.1, 2.3, 2.4, 2.5**

Property 2: Preservation - Everything outside a 2.x monitor mutation is untouched

_For any_ input where the bug condition does NOT hold (isBugCondition returns
false) — every v1.x session, every non-monitor resource and its `delete_*` guard,
the `{}` zero-monitor sentinel path, the #91 string-id paths and every observation
of `wait_for_event` — the fixed library SHALL produce the same result as the
original, preserving the v1.x full-list cache population with the new handlers
inert, the absence of any version lookup on monitor paths, the six unmodified
`delete_*` guards, the sentinel short-circuit to `[]`, the monitor-tag cache
patching under a string key, and the return shapes of `get_monitors()` /
`get_monitor(id)`.

**Validates: Requirements 3.1, 3.2, 3.5, 3.6, 3.7, 3.8, 3.9**

Property 3: Bug Condition - Cache-reading guards decide on fresh data

_For any_ call to `delete_monitor` or `delete_monitor_tag` where the cached view
disagrees with the server (isBugCondition returns true via
`isStaleGuardCondition`), the fixed library SHALL refresh the monitor list from
the server before evaluating the existence check, and SHALL therefore send
`deleteMonitor` / `deleteMonitorTag` for every entity the server actually has —
without consulting `self.version` and without depending on any event having
already been delivered.

**Validates: Requirements 2.2, 2.6, 2.10**

Property 4: Preservation - The guards still reject what does not exist

_For any_ id that genuinely does not exist on the server, in either the int or the
string form, the fixed `delete_monitor` SHALL still raise
`UptimeKumaException("monitor does not exist")` and send nothing, and the fixed
`delete_monitor_tag` SHALL still raise `UptimeKumaException("monitor tag does not
exist")` and send nothing — the refresh makes the guard's input authoritative, it
does not weaken the guard.

**Validates: Requirements 3.3, 3.4**

## Fix Implementation

### Changes Required

Six change groups. Groups 1-3 are the fix; 4-6 are the required cleanup,
documentation and CI bookkeeping.

---

#### 1. Two new `Event` members

**File**: `uptime_kuma_api/event.py`

Add both delta events immediately after `MONITOR_LIST`, so the three
monitor-list events read as a group:

```python
    MONITOR_LIST = "monitorList"
    UPDATE_MONITOR_INTO_LIST = "updateMonitorIntoList"
    DELETE_MONITOR_FROM_LIST = "deleteMonitorFromList"
```

**Decisions:**

- **They deliberately get no `_event_data` entry.** They are handlers that mutate
  the existing `MONITOR_LIST` entry, not events anything waits on. Adding entries
  would create two cache slots nothing ever reads, and — worse — would make
  `wait_for_event(Event.UPDATE_MONITOR_INTO_LIST)` look supported when waiting for
  a delta is exactly the wrong thing to do (the whole point is that no delta is
  guaranteed to arrive). The consequence is that `wait_for_event` /
  `_get_event_data` raise `KeyError` if called with either member; nothing in the
  library does, and nothing should.
- **`Event` is exported, so this is a public-surface question (3.8).** It is
  additive, and `Event` exists precisely to name server events, so the two names
  belong there. It adds no new method, parameter, class or export, and `Event` is
  not in `docs/api.rst`, so the published API reference does not change.

---

#### 2. Two delta-event handlers, plus registration

**File**: `uptime_kuma_api/api.py`

Register alongside the existing block, directly after the `MONITOR_LIST` line
(api.py:508), keeping registration order aligned with handler definition order:

```python
        self.sio.on(Event.MONITOR_LIST, self._event_monitor_list)
        self.sio.on(Event.UPDATE_MONITOR_INTO_LIST, self._event_update_monitor_into_list)
        self.sio.on(Event.DELETE_MONITOR_FROM_LIST, self._event_delete_monitor_from_list)
```

Define both handlers immediately after `_event_monitor_list` (api.py:580):

```python
    def _event_update_monitor_into_list(self, data) -> None:
        # Uptime Kuma 2.x sends this instead of a full monitorList after add,
        # edit, pause, resume and the monitor tag operations. The payload is
        # {id: monitor}, string-keyed like monitorList, with one or more
        # entries. v1.x never emits this event, so this handler is inert there.
        monitors = self._event_data[Event.MONITOR_LIST]
        # rebind rather than mutate: this runs on the socket.io read thread,
        # while _get_event_data copies the same dict on the caller's thread
        updated = {} if monitors is None else dict(monitors)
        for monitor_id, monitor in data.items():
            updated[str(monitor_id)] = monitor
        self._event_data[Event.MONITOR_LIST] = updated

    def _event_delete_monitor_from_list(self, monitor_id) -> None:
        # Uptime Kuma 2.x sends this instead of a full monitorList after a
        # delete, carrying the id alone. One event per monitor, so a group
        # delete that cascades to children arrives as several of these.
        monitors = self._event_data[Event.MONITOR_LIST]
        if monitors is None:
            # No monitorList has arrived yet, so there is nothing to remove.
            # Creating {} here would fabricate the "server has zero monitors"
            # sentinel that _get_event_data relies on, and short-circuit the
            # monitor-scoped events to [] while monitors may well exist.
            return
        updated = dict(monitors)
        updated.pop(str(monitor_id), None)
        self._event_data[Event.MONITOR_LIST] = updated
```

**Decisions:**

- **Payload key coercion is `str(...)` on both sides, unconditionally.** The
  cache is string-keyed (`monitorList` arrives with JSON object keys, and
  `add_monitor_tag` already writes `[str(monitor_id)]`). `updateMonitorIntoList`
  is a JSON object so its keys arrive as strings today, but `str()` on an
  already-string key is a no-op and makes the handler indifferent to a server
  that ever sends them as ints. `deleteMonitorFromList` carries the raw
  `monitor.id`, which arrives as an **int**, so the coercion there is
  load-bearing, not defensive.
- **The handlers store the raw server payload, unparsed.** `get_monitors()` /
  `get_monitor()` apply `_convert_monitor_return`, `int_to_bool` and the `parse_*`
  helpers to a deepcopy on the way out, exactly as they do for `monitorList`
  entries. Parsing inside the handler would double-parse and change return
  shapes (3.9).
- **`None` cache is handled without raising**, mirroring the `add_monitor_tag`
  precedent (api.py:1767) — but asymmetrically, and deliberately: the update
  handler initialises `{}` and then populates it, so the result is never empty;
  the delete handler returns early rather than creating `{}`. See the sentinel
  note below.
- **Copy-then-rebind rather than in-place mutation.** These handlers are the
  first cache writers that run on the socket.io read-loop thread, so a
  concurrent `_get_event_data` doing `.copy()` / `deepcopy` could otherwise
  observe a dict mid-mutation. Rebinding a fully-built dict means a reader sees
  either the old dict or the new one. `add_monitor_tag`'s existing in-place write
  is unaffected — it runs on the caller's thread.

**The `{}` sentinel interaction (3.5, api.py:555).** No part of this fix ever
sets the cache back to `None`, and no part of it clears a populated cache. The
one path that can *produce* `{}` is the delete handler removing the last
remaining monitor — and that is benign, because `{}` then means exactly what the
sentinel says it means: the server has zero monitors, so returning `[]` for
`avgPing`, `uptime`, `heartbeatList`, `importantHeartbeatList`, `certInfo` and
`heartbeat` instead of blocking until timeout is correct, not a collision. The
one path that could produce a *false* `{}` — a delete delta arriving before any
full list — is the case the delete handler's early return exists to prevent.

---

#### 3. A deterministic refresh in the two guards

**File**: `uptime_kuma_api/api.py`

New private helper, placed immediately after `_call` with the rest of the private
plumbing and before the `# event handlers` block:

```python
    def _refresh_monitor_list(self) -> None:
        # Ask the server for a full monitorList and let _event_monitor_list
        # replace the cache with it.
        #
        # This is deterministic, not hopeful: the server's getMonitorList
        # handler emits monitorList and only then acks, socket.io delivers both
        # on this connection in order, and the sync client dispatches events and
        # acks on the same read-loop thread. So _event_monitor_list has already
        # run by the time sio.call returns.
        #
        # Deliberately not version gated: getMonitorList exists in 1.23.X and
        # 2.x, and reading self.version would route through info() ->
        # _get_event_data, whose 0.2s wait_events sleep costs far more than the
        # 2-6ms round trip it would be guarding.
        self._call('getMonitorList')
```

In `delete_monitor` (api.py:1578) and `delete_monitor_tag` (api.py:1798), it
becomes the first statement inside the existing `with`:

```python
        with self.wait_for_event(Event.MONITOR_LIST):
            self._refresh_monitor_list()
            ids = [i["id"] for i in self.get_monitors()]
            ...
```

```python
        with self.wait_for_event(Event.MONITOR_LIST):
            self._refresh_monitor_list()
            tags = [
                ...
            ]
```

**Decisions:**

- **A shared private helper, not two inline `self._call("getMonitorList")`
  lines.** Three reasons, in order of weight. (a) It keeps the multi-paragraph
  ordering-and-no-gating rationale in one place instead of duplicating it — this
  project has already been bitten by duplicated explanations drifting.
  (b) It is the seam the regression tests and the *existing* tests need: a
  `MagicMock(spec=UptimeKumaApi)` stubs `_refresh_monitor_list` out, so
  `tests/test_delete_id_coercion_v2.py`'s
  `api._call.assert_called_once_with("deleteMonitor", 371)` keeps passing
  untouched. An inline `self._call(...)` would add a second `_call` and break
  seven existing assertions for no behavioural reason. (c) If a third caller ever
  needs it, there is one thing to call.
- **Exceptions propagate.** A `Timeout` from the refresh surfaces as the
  library's own `Timeout` (already a documented `:raises:` on both methods via
  `_call`), and a connection sick enough to time out on `getMonitorList` would
  fail the subsequent `deleteMonitor` anyway. Swallowing it would mean deciding
  the guard from data we just failed to refresh — the exact failure mode being
  fixed.
- **It runs inside the `with`, before the read**, so the refreshed list is what
  the guard sees and the diff stays a single inserted line per guard.
- **Cost**: one extra 2-6 ms round trip per `delete_monitor` /
  `delete_monitor_tag` call. `get_monitors()`'s existing 0.2 s `wait_events`
  sleep already dominates both methods.

**Why both halves, not one.** The handlers alone leave the guards dependent on
delivery: a mutation made from the web UI or another client, a
`sendUpdateMonitorIntoList` that early-returns without emitting (it does, when
`list[monitorID]` is falsy), or a delta still in flight leaves the guard deciding
from a cache that was never corrected. The refresh alone leaves `add_monitor`,
`edit_monitor`, `pause_monitor`, `resume_monitor` and every plain `get_monitors()`
read stale, because none of those is a guard and none of them would refresh.

**Post-delete read.** `deleteMonitor` is the one handler that acks *before*
emitting its delta, so the removal lands a few milliseconds after
`delete_monitor` returns rather than before. The next `get_monitors()` picks it
up during `_get_event_data`'s unconditional 0.2 s `wait_events` sleep — roughly a
200x margin over an in-flight packet on a connection whose ack has already been
received. This is deliberately left to the handler rather than also popping the
id locally in `delete_monitor`: a local pop cannot cover the per-child cascade
events a group delete emits, so it would add a second mechanism that is still
incomplete. If live verification ever shows this racing, the fallback is a
`pop` after a successful `_call` — idempotent with the handler, since both are
`pop(key, None)`.

**`pause_monitor` / `resume_monitor` are not modified.** Requirements 1.5 and 2.5
are satisfied with no change to either method: both server handlers emit
`updateMonitorIntoList` before they ack, so by the time `_call` returns the
handler from group 2 has already written the new `active` value into the cache.
Neither method reads the cache, so neither needs a refresh. Leaving them alone is
both correct and the smaller diff.

**The four `wait_for_event(Event.MONITOR_LIST)` wraps stay** (api.py:1578, 1711,
1738, 1798). They are no-ops once login has populated the cache, which is the
overwhelmingly common case, but they are *not* dead: on the first mutation of a
session where the cache is still `None`, the wrap still blocks until a
`monitorList` arrives. Removing them would change v1.x control flow on the fix
path for that case, which preservation (3.1, 3.2) forbids without evidence, and
the coding standards say not to refactor unrelated code alongside a fix. The
misleading part was never the call sites — it was that the helper does not say
what it does, which group 4 fixes in one place instead of four.

---

#### 4. Document `wait_for_event`'s first-event-only semantics (2.7)

**File**: `uptime_kuma_api/api.py` — `wait_for_event` (api.py:533-546)

Replace the single `# waits for the first event of the given type to arrive`
comment with a comment block stating plainly that it waits only for the **first**
event of that type, that it never resets the cached entry, and that it is
therefore a no-op once the entry is populated — so it cannot be used to wait for
a *refresh*, and callers needing fresh data must fetch it (see
`_refresh_monitor_list`).

**Decision: a comment, not a docstring.** `docs/api.rst` autodocs
`UptimeKumaApi`, so a docstring would newly publish `wait_for_event` in the API
reference and present an internal-by-convention context manager as a supported
helper whose semantics callers may then depend on. A comment satisfies 2.7's
"document in place" for the audience that matters — the next maintainer reading
the four wraps — while changing neither the signature nor the runtime behaviour,
as 2.7 requires. (If publishing it is ever wanted, that is a separate,
deliberate documentation change.)

---

#### 5. Remove the temporary scaffolding (2.8)

**File**: `tests/live_test_delete_id.py`

Delete exactly these eight items, and nothing else:

1. The whole `TEMPORARY SCAFFOLDING -- remove when the monitor-list cache defect
   is fixed:` section of the module docstring.
2. The Step 2 staleness probe: the `ids_before_refresh = ...` line through the
   `if monitor_id not in ids_before_refresh:` / `else:` block, including its
   `known_issue(...)` call, its `INFO` print, and the `--- KNOWN ISSUE probe ---`
   comment above it.
3. `api._call("getMonitorList")` #1 — Step 2, before the string-id delete —
   together with its `WORKAROUND for the known cache defect` comment.
4. `api._call("getMonitorList")` #2 — Step 2, before the post-delete
   `get_monitors()` read — together with its `Same WORKAROUND again` comment.
5. `api._call("getMonitorList")` #3 — the cleanup int-id fallback — together with
   its `Same WORKAROUND as Step 2` comment.
6. The `known_issue()` helper function.
7. The module-level `known_issues = []` list.
8. The `if known_issues:` reporting block at the end of `main()`.

**Explicitly kept**: the `skip()` helper (used by the Bug E probe, which is
inconclusive-capable by design), the whole Step 4 Bug E probe, `record()`, the
`results` list and its reporting, the safety notes, and the ASCII-only output
convention.

After removal the script must still pass end to end against a disposable 2.x
instance, with the post-delete `get_monitors()` read seeing the monitor gone on
the library's own behaviour — which is the acceptance test for the whole fix.

---

#### 6. Changelog, compatibility argument, triage note, CI file list

> **CORRECTED by a later commit — there is no 2.3.1 and there will not be one.**
> The section described below was folded into the unreleased `### Release 2.3.0`,
> which is where this entry now lives. Read `2.3.1` as `2.3.0` throughout.

**`CHANGELOG.md`** — a new `### Release 2.3.1` section above `### Release 2.3.0`,
with a `#### Bugfixes` entry and a `#### Notes` entry. The bugfix entry states
the 2.x behaviour change with its server-source citation, the two-halves fix, the
one extra round trip per guarded delete, and that no public API surface changed.
The notes entry carries the **written v1.x compatibility argument (2.10)**
verbatim in substance: the delta handlers are inert on v1.x because v1.x never
emits `updateMonitorIntoList` or `deleteMonitorFromList` and instead keeps sending
the full `monitorList` after every mutation; the guard refresh is unconditional
because `socket.on("getMonitorList")` exists in both 1.23.X and 2.x, and gating
it on `self.version` would route through `info()` → `_get_event_data` and pay a
0.2 s `wait_events` sleep to save a 2-6 ms RPC — so *not* gating is the
v1-friendlier choice, not a shortcut. Also note the judgment call that
`pause_monitor` / `resume_monitor` needed no change. Whether `__version__.py` is
bumped is a release-time decision, not part of this fix.

**`UPSTREAM_TRIAGE.md` section 7** — append a short resolution note recording
which candidate route was taken (1 **and** 2 of the three listed), what was done
about `wait_for_event` (documented, not changed, with the reason), and that the
`live_test_delete_id.py` scaffolding is gone. Keep it to a few lines: the section
is the diagnosis, the design and changelog are the record of the fix, and
section 7's own preamble warns against duplicating the account.

**The CI file list** — adding `tests/test_monitor_cache_v2.py` (see Testing
Strategy) means the list of unit-test files must be updated in **five** places,
all in the same change:

1. `.github/workflows/test.yml` (line ~28) — the only one that actually affects CI
2. `CONTRIBUTING.md` (line ~35)
3. `AGENTS.md` (line ~45)
4. `.kiro/steering/tech.md` (line ~35)
5. `.kiro/steering/structure.md` (line ~25) — prose enumeration of the v2 suite

Two corrections to the brief's assumption, both verified: **`run_tests.sh` carries
no file list** — it runs `python -m unittest discover -s tests` against a Docker
instance and is the inherited integration runner, so it needs no change (discovery
picks the new file up automatically). And `.kiro/steering/testing.md` says "the
six v2 files" while there are currently eight — already stale, and it should be
de-numbered rather than re-counted so it cannot drift again. Anywhere else the
count is spelled out ("the 8-file CI list") becomes nine. This project has been
bitten by exactly this drift before: `test_status_page_incidents.py` was
documented as part of the unit suite for a whole release while never actually
running in CI. All five updates land together or the change is incomplete.

## Testing Strategy

### Validation Approach

Two phases. First, prove the bug on the unfixed code — and be honest about which
tests constitute real evidence. Then verify the fix and, separately, that nothing
outside the bug condition moved.

All regression tests are unit tests in the v2 suite: no live server, transport
and version mocked, following the patterns already in
`tests/test_monitor_params_v2.py` (`MagicMock(spec=UptimeKumaApi)` plus unbound
methods bound with `__get__`) and `tests/test_delete_id_coercion_v2.py` (mocked
`_call`, guard logic exercised for real).

**File**: a new `tests/test_monitor_cache_v2.py`, not an extension of an existing
v2 file. The defect is cohesive and gets one file, matching the
`test_delete_id_coercion_v2.py` precedent from 2.3.0; a reader looking for the
cache-coherence tests should find them by filename. The cost is the five-place CI
list update enumerated in change group 6, which is a known, enumerable cost —
whereas burying twenty cache tests inside `test_monitor_params_v2.py` (a file
about `_build_monitor_data`) is a permanent discoverability cost.

**Two harnesses**, both in the new file:

- *Handler harness* — a `MagicMock(spec=UptimeKumaApi)` with a real
  `_event_data` dict, and the handler under test bound via
  `UptimeKumaApi._event_update_monitor_into_list.__get__(api)`. Asserts on the
  cache dict directly.
- *Guard harness* — the same mock, but with real `wait_for_event`,
  `_get_event_data`, `get_monitors` and `_refresh_monitor_list` bound, plus
  `api.wait_events = 0` and a small `api.timeout` to keep the suite fast. `_call`
  is mocked with a `side_effect` that mimics the server contract: a
  `getMonitorList` call **populates** `api._event_data[Event.MONITOR_LIST]` with
  the fresh dict (exactly as `_event_monitor_list` would), a `deleteMonitor` /
  `deleteMonitorTag` call returns a success dict. This matters: the harness
  refers only to names that exist **before** the fix (`_event_data`, `_call`,
  `wait_events`, `timeout`), so the guard tests can be run against the unfixed
  code and fail for the right reason rather than erroring on a missing attribute.

### Exploratory Bug Condition Checking

**Goal**: surface counterexamples on the unfixed code, and confirm the root-cause
analysis before implementing anything. The analysis is already server-source
confirmed, so the open question is narrower: does the *library-side* mechanism
behave as the diagnosis says — is the cache really never written after a
mutation, and does the guard really reject before sending?

**Test plan**: run the two guard tests below against the unfixed code first, and
re-run the existing `tests/live_test_delete_id.py` staleness probe against a
disposable 2.x instance for the end-to-end counterexample.

**Test cases:**

1. **Guard rejects an id the server has** — `delete_monitor` with the id absent
   from the cache but present in the server's fresh list. Fails on unfixed code
   with `UptimeKumaException: monitor does not exist`, and `_call` is never
   invoked with `deleteMonitor`.
2. **Tag guard rejects a tag the server has** — same shape for
   `delete_monitor_tag`. Fails on unfixed code with `monitor tag does not exist`.
3. **`wait_for_event` is a no-op** — with the cache already populated, the wrap
   returns without waiting, so it cannot be the mechanism that refreshes
   anything. Passes on unfixed code, and is the evidence for decision 3 in the
   requirements (`wait_for_event` semantics unchanged, documented instead).
4. **Delta payloads reach nothing** — asserting the handler methods do not exist
   on the unfixed class. Trivially true; recorded for completeness, not treated
   as evidence.

**Expected counterexamples**: the guard raises for an existing entity and sends
nothing; the cache is never written between mutations. Cause, as diagnosed: no
handler for either delta event, plus a guard that trusts the cache.

### Fix Checking

**Goal**: for all inputs where the bug condition holds, the fixed code produces
the expected behaviour.

**Pseudocode:**

```
FOR ALL input WHERE isBugCondition(input) DO
  result := fixedFunction(input)
  ASSERT expectedBehavior(result)
END FOR
```

Concretely, the two halves:

```
// Property 1 - delta handlers keep the cache coherent
FOR ALL mutation m ON a 2.x server DO
  deliver(delta_event_for(m))
  ASSERT cached_monitor_list() = server_monitor_list()
END FOR

// Property 3 - guards decide on fresh data
FOR ALL guard g IN {delete_monitor, delete_monitor_tag} DO
  ASSERT refresh_called_before_read(g)
  ASSERT (target IN server_state) IMPLIES request_sent(g)
END FOR
```

### Preservation Checking

**Goal**: for all inputs where the bug condition does NOT hold, the fixed code
produces the same result as the original.

**Pseudocode:**

```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT originalFunction(input) = fixedFunction(input)
END FOR
```

**Testing approach**: generated-input testing is used where the input domain is
wide enough to hide an edge case — id sets, key types, cache states — following
the seeded `random.Random` idiom already established in
`tests/test_delete_id_coercion_v2.py` (Hypothesis is deliberately not a project
dependency; a fixed seed keeps CI reproducible).

**Test plan**: observe the behaviour on the unfixed code first for every
non-bug-condition input, then assert that behaviour still holds after the fix.
The strongest preservation signal is free: `tests/test_delete_id_coercion_v2.py`'s
seven `delete_monitor` assertions, including
`api._call.assert_called_once_with("deleteMonitor", 371)`, must keep passing
**unmodified**. That is why the refresh is a stubbable helper (change group 3).

**Test cases:**

1. **The existing coercion suite is untouched** — `test_delete_id_coercion_v2.py`
   passes with no edits, proving the guard's observable contract for both int and
   string ids is unchanged at all seven sites.
2. **v1.x is inert** — the delta handlers are never registered as *reachable*
   behaviour on a v1.x server because v1.x never emits those events; asserted by
   showing the cache after a simulated v1.x full-list broadcast is byte-identical
   to today's, with no handler invocation.
3. **No version lookup on the fix path** — `_refresh_monitor_list` must not touch
   `self.version`, `_parsed_version()` or `info()`.
4. **Sentinel short-circuit** — `_get_event_data` with a `{}` monitor list still
   returns `[]` for all six monitor-scoped events.
5. **Monitor-tag cache patching** — `add_monitor_tag` / `delete_monitor_tag`
   still write the target monitor under its string key.

### Unit Tests

`tests/test_monitor_cache_v2.py`. Each test names the requirement clause it
covers; the *pre-fix* column says what happens when it is run against the unfixed
code.

**Delta handler tests** (handler harness):

| # | Test | Covers | Pre-fix |
|---|---|---|---|
| 1 | update handler merges a new id into a populated cache | 1.1, 2.1 | errors (no handler) |
| 2 | update handler merges a multi-entry payload | 2.1 | errors |
| 3 | update handler replaces an existing entry with post-edit values | 1.4, 2.4 | errors |
| 4 | update handler reflects a changed `active` flag (pause/resume) | 1.5, 2.5 | errors |
| 5 | update handler initialises a `None` cache without raising | 2.1, 3.7 | errors |
| 6 | update handler coerces int payload keys to `str` | 2.1 | errors |
| 7 | delete handler removes an entry given an **int** id | 1.3, 2.3 | errors |
| 8 | delete handler removes an entry given a **string** id | 2.3 | errors |
| 9 | delete handler on an absent id is a no-op, cache unchanged | 2.3 | errors |
| 10 | delete handler on a `None` cache leaves it `None`, never `{}` | 3.5 | errors |
| 11 | delete handler removing the last monitor leaves `{}`, and the sentinel still short-circuits to `[]` | 3.5 | errors |
| 12 | both handlers rebind rather than mutate the dict a reader may hold | 3.5, 3.9 | errors |
| 13 | generated cache states x id types: update then delete round-trips to the starting cache | 2.1, 2.3 | errors |

Tests 1-13 fail pre-fix only because the handlers do not exist yet — an
`AttributeError`, which is weak evidence. They are correctness tests for new
code, not the proof that the bug was real.

**Guard tests** (guard harness) — these are the meaningful pre-fix failures:

| # | Test | Covers | Pre-fix |
|---|---|---|---|
| 14 | `delete_monitor` sends `deleteMonitor` for an id present only **after** a refresh | 1.2, 2.2 | **FAILS**: `UptimeKumaException: monitor does not exist`, `deleteMonitor` never sent |
| 15 | `delete_monitor_tag` sends `deleteMonitorTag` for a tag present only **after** a refresh | 1.6, 2.6 | **FAILS**: `monitor tag does not exist`, nothing sent |
| 16 | `delete_monitor` with a genuinely absent id still raises `monitor does not exist` and sends no delete | 3.3 | passes |
| 17 | `delete_monitor("7")` for an existing monitor 7 still succeeds; `delete_monitor("not-an-id")` still raises `UptimeKumaException`, not `ValueError` | 3.4 | passes |
| 18 | `delete_monitor_tag` with an absent tag still raises and sends nothing | 3.3 (tag analogue) | passes |
| 19 | `_refresh_monitor_list` issues exactly one `getMonitorList` and touches no version accessor | 2.10, 3.2 | errors (no helper) |
| 20 | `wait_for_event` with a populated entry returns without waiting (documents the no-op the comment now states) | 1.7, 2.7 | passes |

Tests 14 and 15 are the two that satisfy requirement 2.9's "demonstrated to fail
against the unfixed code": they use only pre-existing names, exercise the real
guard bodies, and fail with the exact production exception. Tests 16-18, 20 are
the preservation baseline and pass both before and after — which is the point.

### Property-Based Tests

Seeded-generator tests over the input domains where an edge case could hide,
following `test_delete_id_coercion_v2.py`'s `generated_id_cases()` idiom:

- **Cache-coherence round trip** (Property 1) — generate random cache states
  (empty, single, many monitors; string keys) and random delta payloads (int or
  string keys, one or many entries); assert the cache after applying the delta
  equals the expected merged/reduced dict, and that a delete of everything just
  added returns the cache to its starting value.
- **Guard correctness across id sets** (Properties 3, 4) — generate
  (stale_ids, fresh_ids, target_id) triples; assert `delete_monitor` sends the
  delete for every target in `fresh_ids` regardless of `stale_ids`, and raises
  without sending for every target in neither, for both int and string forms.
- **Sentinel invariance** (Property 2) — across generated handler call sequences,
  assert the cache is never set to `None` after having been populated, and that
  `{}` occurs only when the monitor count genuinely reached zero.

### Integration Tests

Manual, against a disposable 2.x instance, not CI:

- `tests/live_test_delete_id.py` with all scaffolding removed (change group 5) —
  the acceptance test for the whole fix: create, `get_monitors()` sees the new id
  with no `_call("getMonitorList")` workaround, string-id delete, post-delete
  `get_monitors()` sees it gone, exit code 0.
- A pause/resume/edit round trip — mutate, then `get_monitors()` and confirm the
  post-mutation `active` value and edited fields, with no refresh call, proving
  the handler covers the untouched methods (1.4, 1.5, 2.4, 2.5).
- `tests/live_test_create.py` then `tests/live_test_cleanup.py --dry-run` then
  the real cleanup — confirms the monitor-tag paths and the six unrelated
  `delete_*` guards still behave (3.6, 3.7).
- Optional, if a 1.23.X container is available: the same create/delete cycle on
  v1.x, confirming the full-list broadcast still drives the cache and the delta
  handlers never fire (3.1, 3.2).
