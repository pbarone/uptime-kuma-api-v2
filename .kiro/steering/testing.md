# Testing standards

Always included. It was previously `inclusion: fileMatch` on `tests/**/*.py`,
which meant the ASCII-output rule below — the only place it is recorded outside a
gitignored file — did not load until a test file happened to be in context.

## Where tests go

New unit and regression tests go in the **v2 unit suite** (the `*_v2.py` files
plus `test_status_page_incidents.py`, `test_monitor_builder.py`). These run
without a live server and are what CI executes. Do not add server-dependent
tests to the CI path.

## A regression test must be able to fail

When fixing a bug, prove the test actually catches it: revert the fix, watch the
new test go red, then restore the fix. A test that has only ever passed proves
nothing. (This caught real value on the `incidents` fix — the 10 tests were
confirmed to fail against the pre-fix code.)

## Mock the server for unit tests

Unit tests mock the version and transport (see `test_status_page_v2.py`,
`test_status_page_incidents.py`) — e.g. set `api.version` and patch
`requests.get` / the socket.io call. Test both a v1 and a v2 `version` where
behavior is version-gated, so the backward-compat contract is covered.

## Never wipe a real instance

Do NOT run `pytest tests/` (bare) or the inherited integration tests against any
instance you care about — their setup deletes all data. Name the v2 unit files
explicitly — the authoritative list is the `pytest` command in `CONTRIBUTING.md`
(mirrored in `.github/workflows/test.yml`, which is the one CI actually reads) —
or use a disposable Docker instance.

## Live verification (manual, real 2.x server)

For end-to-end checks against a real instance, use the scripted cycle and always
back up and dry-run first:

```
python tests/live_test_backup.py            # config snapshot first
python tests/live_test_create.py            # create + round-trip verify
python tests/live_test_cleanup.py --dry-run # ALWAYS dry-run before deleting
python tests/live_test_cleanup.py
```

The live create script's value is the **round-trip**: create a resource, read it
back, and compare sent vs returned fields (ABSENT vs MISMATCH). "The server
didn't reject it" is not verification.

## Live verification against v1 (separate, do not mix into the cycle above)

`tests/live_test_conditions_v1.py` is a standalone one-off, **not** a step in the
2.x cycle. It targets a disposable Uptime Kuma **1.23.x** container and reads its
own `UPTIME_KUMA_V1_URL` / `UPTIME_KUMA_V1_USERNAME` / `UPTIME_KUMA_V1_PASSWORD`
keys, not the `tests/.env` 2.x keys — so it must never be appended to the
backup → create → cleanup sequence, which would point it at the wrong server.

```
docker run -d --name kuma-v1-conditions -p 3023:3001 louislam/uptime-kuma:1.23.2
python tests/live_test_conditions_v1.py     # disposable v1 container only
```

It creates monitors and deletes them again in a `finally` block, so no
`live_test_cleanup.py` pass is needed — but throw the container away afterwards
anyway (`docker rm -f kuma-v1-conditions`). It refuses to run with the URL unset
and aborts unless the server reports `1.23`, so a mistargeted URL fails closed
rather than mutating a 2.x instance.

## Script output must be ASCII

Test/utility scripts print to a Windows cp1252 console. Do not use non-ASCII
glyphs (check marks, box-drawing) in script output — they raise
`UnicodeEncodeError` and have crashed a script mid-run. Use `PASS`/`FAIL`/`->`.
