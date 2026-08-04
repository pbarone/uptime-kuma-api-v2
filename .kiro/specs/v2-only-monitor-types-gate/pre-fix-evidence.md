# Pre-fix evidence

The four-type list in [#12](https://github.com/pbarone/uptime-kuma-api2/issues/12)
was **unverified** when this spec opened. Nothing in the repository established
which server version first implemented `RABBITMQ`, `SNMP`, `SMTP` or
`SYSTEM_SERVICE`, and the `.kiro/specs/conditions-field-v1-regression/` design
declined to raise for seven adjacent v2-only *fields* precisely because their
failure on v1 was unverified — raising there "would convert a possibly-working
path into a guaranteed hard error".

That objection has to be discharged with evidence before this fix can raise, so
this document establishes two things separately:

1. **Provenance** — when upstream added each type (source history and tags).
2. **Observed v1 behaviour** — what a real 1.23.x server does when asked for
   one, including the case where the type's companion fields are *not* on the
   wire.

Point 2 turned out to matter more than expected: it **corrects the premise of
issue #12** and of one supporting sentence in the conditions design. See
`## The correction` below.

## Provenance: all four types are 2.x-only

Method per `.kiro/steering/tech.md`: Uptime Kuma's own source and tags, not
secondary summaries. Full clone of `louislam/uptime-kuma` at `master`
(`948fdd78`), 2026-08-03.

Each type is implemented by one file under `server/monitor-types/`. The commit
that added that file, and the earliest release tag containing it:

| `MonitorType` | type string | adding commit | date | first tag | 1.x tags containing it |
|---|---|---|---|---|---|
| `RABBITMQ` | `rabbitmq` | `c01494ec` feat: add `RabbitMQ` monitor (#5199) | 2024-10-20 | **2.0.0** (via `2.0.0-beta.0`) | **0** |
| `SNMP` | `snmp` | `d92003e1` SNMP Initial Commits | 2024-04-26 | **2.0.0** (via `2.0.0-beta.0`) | **0** |
| `SMTP` | `smtp` | `c67f6efe` added SMTP monitor (#5489) | 2025-05-18 | **2.0.0** (via `2.0.0-beta.3`) | **0** |
| `SYSTEM_SERVICE` | `system-service` | `0f951ef1` Added Windows Service Monitor & changed local to systen | 2025-12-15 | **2.1.0** (via `2.1.0-beta.1`) | **0** |

Commands used:

```
git log --diff-filter=A --format="%H|%ad|%s" --date=short -- server/monitor-types/<file>.js
git tag --contains <commit>
git tag --contains <commit> | grep '^1\.'      # empty for all four
```

Cross-check against the newest 1.x tag, `1.23.17` — the highest version any
v1.x user can be running:

```
git grep -i rabbitmq       1.23.17 -- server/ src/   # no matches
git grep -i snmp           1.23.17 -- server/ src/   # no matches
git grep -i system-service 1.23.17 -- server/ src/   # no matches
git grep    '"smtp"'       1.23.17 -- server/ src/   # matches ONLY the
                                                     # NOTIFICATION provider
```

The `smtp` result is the one trap in the list: the string does exist in 1.x, as
`server/notification-providers/smtp.js` (the "Email (SMTP)" notification
provider) and its translations. There is no `smtp` **monitor** type in 1.x.

**Verdict on the list: #12's four types are correct.** All four are 2.x-only,
and `SYSTEM_SERVICE` is in fact 2.1-only — stricter than the gate this fix
applies. See `## Why the gate is 2.0 and not per-type` in `design.md`.

## Observed behaviour against a real 1.23.x server

Disposable container on the Docker host described in
`.kiro/steering/tech.md`, on a port verified free before use (3001, 3022 and
80/81/443 are taken on that host; 3023 was used by the earlier conditions run):

```
docker run -d --name kuma-v1-mtypes -p 3024:3001 louislam/uptime-kuma:1.23.17
```

`1.23.17` rather than the `1.23.2` in the steering example, deliberately: if a
type is absent from the *newest* 1.x release it is absent from all of them.

Probed with two throwaway scripts kept in `TEMP` and never committed. They are
not tracked because neither is a repeatable deliverable — their only product is
the verbatim output below. Both create monitors and delete them in a `finally`
block; the container was destroyed afterwards with `docker rm -f`.

Server reported `1.23.17`. Credentials came from the `UPTIME_KUMA_V1_*` keys in
the gitignored `tests/.env`, pointing at `http://<docker-host>:3024/`.

### Probe 1 — the four types through the real public method

`add_monitor(type=..., <that type's required fields>)`, verbatim:

```
login(): OK, server reports version 1.23.17
--------------------------------------------------------------------
RABBITMQ  (type string 'rabbitmq')
--------------------------------------------------------------------
  add_monitor -> UptimeKumaException: insert into `monitor` (... `rabbitmq_nodes`,
  `rabbitmq_password`, `rabbitmq_username`, ...) values (...) - SQLITE_ERROR:
  table monitor has no column named rabbitmq_nodes
--------------------------------------------------------------------
SNMP  (type string 'snmp')
--------------------------------------------------------------------
  add_monitor -> UptimeKumaException: insert into `monitor` (... `snmp_oid`,
  `snmp_version`, ...) values (...) - SQLITE_ERROR: table monitor has no column
  named snmp_oid
--------------------------------------------------------------------
SMTP  (type string 'smtp')
--------------------------------------------------------------------
  add_monitor -> UptimeKumaException: insert into `monitor` (... `smtp_security`,
  ...) values (...) - SQLITE_ERROR: table monitor has no column named
  smtp_security
--------------------------------------------------------------------
SYSTEM_SERVICE  (type string 'system-service')
--------------------------------------------------------------------
  add_monitor -> UptimeKumaException: insert into `monitor` (...
  `system_service_name`, ...) values (...) - SQLITE_ERROR: table monitor has no
  column named system_service_name
--------------------------------------------------------------------
Control: a type that IS in 1.x (HTTP)
--------------------------------------------------------------------
  add_monitor -> {'msg': 'Added Successfully.', 'monitorID': 1}
  last heartbeat: status=<MonitorStatus.PENDING: 2> msg='connect ECONNREFUSED
  127.0.0.1:80'
```

(The `insert into` statements are elided at `...` for width; the full column
lists were captured and every one of the four ends in the quoted
`SQLITE_ERROR`.)

So all four fail today — but **look at what the server is objecting to**. Not
the `type` value. A missing *column*, named in snake_case, for the type's
companion field. That is a schema collision on an adjacent parameter, not a
verdict on the type.

### Probe 2 — the type string in isolation

The question probe 1 cannot answer, and the one that decides whether a
type-level gate is independently necessary: **if the companion fields were not
on the wire, would a 1.23.x server accept the type?**

This bypasses `_build_monitor_data` and puts a minimal payload containing only
columns the 1.23.x schema actually has on the wire, via `api._call("add", ...)`,
with nothing but `type` varying. Verbatim:

```
login(): OK, server reports version 1.23.17
--------------------------------------------------------------------
bare type 'rabbitmq'  (no v2-only companion columns on the wire)
--------------------------------------------------------------------
  add -> ACCEPTED BY SERVER: {'msg': 'Added Successfully.', 'monitorID': 2}
  last heartbeat: status=<MonitorStatus.PENDING: 2> msg='Unknown Monitor Type'
--------------------------------------------------------------------
bare type 'snmp'  (no v2-only companion columns on the wire)
--------------------------------------------------------------------
  add -> ACCEPTED BY SERVER: {'msg': 'Added Successfully.', 'monitorID': 3}
  last heartbeat: status=<MonitorStatus.PENDING: 2> msg='Unknown Monitor Type'
--------------------------------------------------------------------
bare type 'smtp'  (no v2-only companion columns on the wire)
--------------------------------------------------------------------
  add -> ACCEPTED BY SERVER: {'msg': 'Added Successfully.', 'monitorID': 4}
  last heartbeat: status=<MonitorStatus.PENDING: 2> msg='Unknown Monitor Type'
--------------------------------------------------------------------
bare type 'system-service'  (no v2-only companion columns on the wire)
--------------------------------------------------------------------
  add -> ACCEPTED BY SERVER: {'msg': 'Added Successfully.', 'monitorID': 5}
  last heartbeat: status=<MonitorStatus.PENDING: 2> msg='Unknown Monitor Type'
--------------------------------------------------------------------
bare type 'definitely-not-a-real-type'  (no v2-only companion columns)
--------------------------------------------------------------------
  add -> ACCEPTED BY SERVER: {'msg': 'Added Successfully.', 'monitorID': 6}
  last heartbeat: status=<MonitorStatus.PENDING: 2> msg='Unknown Monitor Type'
```

A 1.23.x server accepts an unrecognised monitor type, answers
`Added Successfully.`, and creates a monitor that sits `PENDING` forever
reporting `Unknown Monitor Type`. The invented control type behaves identically
to the four real ones, which is the proof that the type value itself is never
validated.

### Corroboration in the 1.23.17 source

The observed behaviour is exactly what the code says it should be.

`server/server.js`, the `add` handler (line 643) validates
`accepted_statuscodes` and calls `bean.validate()` — and
`server/model/monitor.js:1578` is:

```js
/** Make sure monitor interval is between bounds */
validate() {
    if (this.interval > MAX_INTERVAL_SECOND) { ... }
    if (this.interval < MIN_INTERVAL_SECOND) { ... }
}
```

Interval bounds only. **Nothing on the add path validates `type`.**

The type is first consulted at *beat* time, at the end of the long
`if (this.type === ...)` chain in `monitor.js`:

```js
} else {
    throw new Error("Unknown Monitor Type");
}
```

which is caught per-beat and recorded as the heartbeat message. Hence
`PENDING` + `Unknown Monitor Type` rather than an error to the caller.

## The correction

Issue #12 says of the current behaviour:

> It currently **fails loudly at the server**: the caller explicitly asked for a
> monitor type their server cannot support, and gets an error.

The first half is right by accident and the second half is wrong about the
mechanism. The caller does get an error today, but:

- It is not the server rejecting the **type**. The server has no opinion on the
  type at add time — probe 2 proves it, `validate()` confirms it.
- It is a `SQLITE_ERROR` naming a snake_case **column** (`rabbitmq_nodes`,
  `snmp_oid`, `smtp_security`, `system_service_name`) that the caller never
  typed and cannot map to a parameter without reading library source.
- The rejection only happens because the library *also* sends that column. It
  is a side effect of the companion-field payload, not a guarantee.

`.kiro/specs/conditions-field-v1-regression/design.md` carries the same
mechanical error in one supporting sentence:

> For `snmp_v3_username` the gate is close to a no-op anyway: the `SNMP` monitor
> type is itself v2-only, so a v1 server rejects the monitor type before the
> field matters.

The conclusion (gate it, expect no behavioural change) stands. The stated reason
does not: a v1 server does not reject the type. It rejects `snmp_oid`, and only
because `snmp_oid` is sent.

## What this evidence establishes

1. **The four-type list is correct and complete for a 2.0 gate.** All four are
   2.x-only in upstream source and appear in no 1.x tag.
2. **There is no working path to preserve.** On any 1.x server, both reachable
   outcomes are failures: an opaque `SQLITE_ERROR` (today) or a permanently
   `PENDING` monitor reporting `Unknown Monitor Type` (with the companion fields
   absent). A 1.x server has no implementation of these types, so no caller can
   have a working one. This is the fact that discharges the conditions design's
   objection — the raise cannot convert a working call into a hard error,
   because no working call exists.
3. **A type gate is independently necessary, not a duplicate of a field gate.**
   Today's rejection is a byproduct of the companion fields. If #14 later gates
   v2-only fields silently — its most likely outcome, and what backlog
   requirement 13.3 already prescribes for fields — that byproduct disappears
   and these calls start *succeeding* into permanently-`PENDING` monitors. The
   type gate is what stops #14 from opening a silent hole.
4. **The failure mode the gate replaces is worse than #12 described**, in both
   directions: today's error is opaque and misattributed, and tomorrow's (post-
   #14) would be silent.
