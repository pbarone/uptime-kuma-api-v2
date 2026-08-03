# Live verification evidence -- requirement 2.8

Requirement 2.8 is the acceptance gate for this spec: **`add_monitor()` succeeds
against a live Uptime Kuma 1.23.2 server through the real public method, with no
`pop("conditions")` workaround** -- the workaround that was needed to make the
original discovery run complete. Task 12's unit checkpoint proves the change is
internally correct but explicitly does **not** close 2.8; this file does.

This is the artifact for the v1 half of task 13: the verbatim output of
`tests/live_test_conditions_v1.py` run against a fresh, disposable
`louislam/uptime-kuma:1.23.2` container.

Copy the "Verbatim script output" section below into the PR description
alongside `pre-fix-evidence.md`.

## Provenance

| | |
|---|---|
| Recorded by | task 13 (v1 half) of the `conditions-field-v1-regression` bugfix spec |
| Recorded at | 2026-08-01 17:06:02 -04:00 (the captured run; an earlier identical run a few minutes prior -- see the notes at the end) |
| Code state | **fixed** -- branch `release/2.3.0` with the conditions gate applied, working tree clean. No commit SHA is cited: this branch's history was rewritten after the run (see the note below), so the hash recorded at the time no longer exists. `_check_conditions_supported` at `api.py:778`, call sites at `api.py:969` (`_build_monitor_data`, directly after the `TypeError` check) and `api.py:1818` (`edit_monitor`, first statement), `data["conditions"]` assigned at `api.py:1225` inside the existing `if self._parsed_version() >= parse_version("2.0"):` block |
| Command | `.venv\Scripts\python.exe tests\live_test_conditions_v1.py` |
| Target | `http://<docker-host>:3023` -- disposable container `kuma-v1-conditions`, `docker run -d --rm --name kuma-v1-conditions -p 3023:3001 louislam/uptime-kuma:1.23.2`, **no volume mount** |
| Credentials | throwaway, supplied as process-level `UPTIME_KUMA_V1_URL` / `UPTIME_KUMA_V1_USERNAME` / `UPTIME_KUMA_V1_PASSWORD` for the single invocation. **Not** written to `tests/.env` (that file holds the 2.x config). Values never printed |
| Environment | Windows, Python 3.13.3, python-socketio 5.16.3, `uptime_kuma_api` 2.3.0 from the working tree; Docker 29.7.1 on the container host |
| Result | **14 passed, 0 failed, 14 checks total**, exit code **0** |

The address of the container host has been replaced throughout this file with
the placeholder `<docker-host>`, including inside the otherwise-verbatim script
output below. That substitution was applied by rewriting the commits on this
branch that introduced the address, so the commit hashes recorded at the time of
the run no longer exist and the "Code state" row above describes the code
without citing one. Those are the only edits made after the run: no recorded
result, count, `monitorID`, version string, `PASS` line or exit code has been
altered.

### Server version, verified independently of the script

The script's own Step 2 guard aborts unless the server reports a `1.23` prefix,
and it passed (`version 1.23.2`). Because the entire run is meaningless against
a v2 instance, the version was also confirmed from outside the library:

| Source | Value |
|---|---|
| Image tag (`docker inspect --format '{{.Config.Image}}'`) | `louislam/uptime-kuma:1.23.2` |
| Image digest | `sha256:8d35ad2f33a6f24f8e942b5a6eb6856e3aa5b4d89ad16ce0e6edfbc53bcb4624` |
| In-container `/app/package.json` | `"version": "1.23.2",` |
| Server reported over the API (`api.version`) | `1.23.2` |

Four independent sources agree, so the run was not against a cached different
tag.

## Verdict: requirement 2.8 is SATISFIED

`add_monitor(type=HTTP, name="v1-conditions-gate", url="http://127.0.0.1")` --
no `conditions` argument, no `pop("conditions")` -- returned

```
{'msg': 'Added Successfully.', 'monitorID': 1}
```

against Uptime Kuma **1.23.2**. Pre-fix this same call was rejected with
`SQLITE_ERROR: table monitor has no column named conditions`.

## Per-check verdict

All fourteen checks passed. Mapped to what task 13 and the design's Live
Verification Plan require:

| # | Check | Result | What it evidences |
|---|---|---|---|
| 1 | `setup()` bootstrapped the fresh container | PASS | fresh container, no pre-existing state; the run is not inheriting a schema from an earlier attempt |
| 2 | `login` | PASS | `server reports version 1.23.2` |
| 3 | server version starts with `1.23` | PASS | the script's own abort guard; `version 1.23.2` |
| 4 | `add_monitor(type=HTTP)` returns `'Added Successfully.'` with a `monitorID` | PASS | **requirement 2.8, the acceptance criterion.** `{'msg': 'Added Successfully.', 'monitorID': 1}` |
| 5 | monitor `v1-conditions-gate` (id=1) round-trip | PASS | `get_monitor(1)` returned `type`, `name` and `url` matching what was sent -- no ABSENT, no MISMATCH. "The server didn't reject it" is not verification, per the testing standards |
| 6 | v1 server does not return a `conditions` field | PASS | nothing unsupported was persisted; the v1 schema has no such column to echo back |
| 7 | `add_monitor(type=PING)` returns `'Added Successfully.'` with a `monitorID` | PASS | `{'msg': 'Added Successfully.', 'monitorID': 2}` -- the fix is not HTTP-specific (requirements 2.1, 2.2) |
| 8 | monitor `v1-conditions-gate-ping` (id=2) round-trip | PASS | `type`, `name` and `hostname` returned intact |
| 9 | `add_monitor(conditions=[...])` raises `UptimeKumaException` | PASS | `conditions requires Uptime Kuma 2.0 or newer, but the server reports version 1.23.2` -- names the field, the required version and the observed version (requirement 2.3) |
| 10 | ... and no monitor was created | PASS | `get_monitors()` diff empty -- the guard fired before any server call |
| 11 | `edit_monitor(1, interval=120)` succeeds | PASS | `{'msg': 'Saved.', 'monitorID': 1}` -- **requirement 3.6 on a real v1 server**; the new guard does not interfere with the merge path |
| 12 | `interval` persisted on monitor 1 | PASS | round-trip confirms `interval` is really 120, not merely accepted |
| 13 | `edit_monitor(1, conditions=[...])` raises `UptimeKumaException` | PASS | same message, so both call sites enforce identically (requirement 2.5) |
| 14 | ... and no monitor was created | PASS | guard precedes `get_monitor(id_)` |

Exception message observed at both call sites, verbatim:

```
conditions requires Uptime Kuma 2.0 or newer, but the server reports version 1.23.2
```

It names all three required elements -- the field `conditions`, the required
version `2.0`, and the observed version `1.23.2`.

## What this adds over the unit suite

The unit suite (213 passed, 1162 subtests) proves `_build_monitor_data` emits no
`conditions` key on a **mocked** `1.23.2` version string. It cannot prove the
resulting payload is one a real v1 server accepts, because no real server is
involved: the shape of the SQLITE rejection lives in Uptime Kuma's schema, not
in the library. This run closes that gap end to end -- real socket.io transport,
real v1 schema, real insert, and a read-back comparison of what was stored
against what was sent.

## Teardown

```
docker rm -f kuma-v1-conditions
```

Confirmed afterwards:

- `docker ps -a --filter name=kuma` lists only `kuma-disposable`
  (`louislam/uptime-kuma:2`, port 3022) and `uptime-kuma`
  (`louislam/uptime-kuma:2`, port 3001), both still `Up ... (healthy)` with
  their pre-run uptimes. Neither was touched.
- Nothing is listening on port 3023.
- The container ran with `--rm` and **no volume**, so removing it destroyed all
  of its state. Nothing was shared with the other instances on that host.

The two monitors the script created were also deleted by its own `finally`
block (`deleted monitor 1`, `deleted monitor 2`) before the container was
removed, so no `live_test_cleanup.py` pass was needed.

## Verbatim script output

```
Target: http://<docker-host>:3023
This script CREATES monitors. Disposable v1 containers ONLY.

Connecting to http://<docker-host>:3023 ...

Step 1: bootstrap and login
  PASS  setup() bootstrapped the fresh container
          credentials taken from UPTIME_KUMA_V1_USERNAME / _PASSWORD
  PASS  login
          server reports version 1.23.2

Step 2: the server must be a 1.23.x instance
  PASS  server version starts with 1.23
          version 1.23.2

Step 3: add_monitor() with no conditions argument -- the acceptance criterion
  PASS  add_monitor(type=HTTP) returns 'Added Successfully.' with a monitorID
          server response: {'msg': 'Added Successfully.', 'monitorID': 1}

Step 4: round-trip the created monitor
  PASS  monitor v1-conditions-gate (id=1)
  PASS  v1 server does not return a conditions field

Step 5: the same add for a second monitor type (not HTTP-specific)
  PASS  add_monitor(type=PING) returns 'Added Successfully.' with a monitorID
          server response: {'msg': 'Added Successfully.', 'monitorID': 2}
  PASS  monitor v1-conditions-gate-ping (id=2)

Step 6: explicit conditions on add_monitor is rejected
  PASS  add_monitor(conditions=[...]) raises UptimeKumaException
          raised UptimeKumaException -> conditions requires Uptime Kuma 2.0 or newer, but the server reports version 1.23.2
  PASS  add_monitor(conditions=[...]) raises UptimeKumaException -- no monitor was created

Step 7: edit_monitor() without conditions still works
  PASS  edit_monitor(1, interval=120) succeeds
          server response: {'msg': 'Saved.', 'monitorID': 1}
  PASS  interval persisted on monitor 1

Step 8: explicit conditions on edit_monitor is rejected
  PASS  edit_monitor(1, conditions=[...]) raises UptimeKumaException
          raised UptimeKumaException -> conditions requires Uptime Kuma 2.0 or newer, but the server reports version 1.23.2
  PASS  edit_monitor(1, conditions=[...]) raises UptimeKumaException -- no monitor was created

Cleanup
  deleted monitor 1
  deleted monitor 2
  disconnected
  the container itself is disposable: docker rm -f kuma-v1-conditions

============================================================
  14 passed, 0 failed, 14 checks total
============================================================
```

Exit code: `0`.

## Notes on how this run was conducted

- **The run was performed twice**, both times all-PASS with exit code 0. The
  first was against the container as originally started; the console capture of
  that run collapsed the script's blank separator lines, so the container was
  destroyed, started fresh from the same image, and the script re-run with
  output redirected to a file so the block above is byte-faithful. Both runs
  bootstrapped a fresh container via `need_setup()` / `setup()` and both
  reported `monitorID` 1 and 2, which is itself a small consistency check --
  the ids restart from 1 because no state survives `--rm` with no volume.
- **`tests/.env` was not modified.** The three `UPTIME_KUMA_V1_*` keys were set
  as process environment variables for the single invocation and removed
  afterwards. `tests/.env` contains only the 2.x keys (`UPTIME_KUMA_URL`,
  `UPTIME_KUMA_USERNAME`, `UPTIME_KUMA_PASSWORD`, `UPTIME_KUMA_SELFSIGNED_URL`),
  so `load_dotenv` supplied nothing for this script and the process
  environment was the only source -- confirming the script cannot accidentally
  reach the 2.x instance.
- **Repeatability**: persisting the `UPTIME_KUMA_V1_*` keys in `tests/.env`
  would make a re-run a single command, but the URL and credentials are
  specific to a container that no longer exists, and the deliberate absence of
  those keys from that file is what guarantees the script fails closed rather
  than defaulting anywhere. Left for the user to decide.
- **No bare `pytest tests/`** was run, and the inherited integration tests were
  not run against anything (requirement 2.11).
- Port 3023 was confirmed free before starting (3001 and 3022 hold the two
  existing Kuma instances; Nginx Proxy Manager holds 80, 81 and 443).
