# Scripts

Development-time tools for discovering Uptime Kuma field changes.

## Setup

The scripts parse Uptime Kuma's Vue/JS source to detect new monitor fields,
notification providers, etc. You need a local checkout of the Uptime Kuma source:

```bash
# Clone the v2 branch (or a specific tag like v2.4.0)
git clone --depth 1 --branch 2 https://github.com/louislam/uptime-kuma.git scripts/uptime-kuma

# For comparison against an older version:
git clone --depth 1 --branch 1.23.16 https://github.com/louislam/uptime-kuma.git scripts/uptime-kuma-old
```

These directories are gitignored — they won't be committed.

## Live verification against a throwaway server

`run_disposable_kuma.ps1` starts a disposable Uptime Kuma container on a remote
Docker host, runs one `tests/live_test_*.py` script against it, and destroys the
container again:

```powershell
pwsh -File scripts/run_disposable_kuma.ps1 -Script tests/live_test_v2_only_fields_v1.py
```

Use it for the checks that can only be answered by a real server — whether a
version gate is correct, what the server does with a field the library withholds,
how a payload round-trips. It is what produced
`.kiro/specs/v2-only-fields-rule/v1-verification-results.md`.

Two things it does that are easy to get wrong by hand:

- **The container is removed in a `finally` block**, including when the script
  raises or readiness times out. A forgotten container holding a bound port on a
  shared host is the failure this prevents.
- **The Docker host and SSH user are never printed.** They are read from the
  gitignored root `.env` (`DOCKER-HOST` / `DOCKER-USER`) and every line of output
  is rewritten to `<docker-host>` / `<user>`, so a transcript can be pasted into
  an issue or a spec without scrubbing.

It also refuses port 3001 outright — that is the default Uptime Kuma port and
where a real instance is expected to live. The admin password is generated per
run rather than defaulted to a literal, so no credential is committed.

Requires `DOCKER-HOST` and `DOCKER-USER` in the root `.env`, key-based SSH to
that host, and Docker on it. Run `Get-Help scripts/run_disposable_kuma.ps1
-Detailed` for the full parameter list.

## Scripts

- `run_disposable_kuma.ps1` — Runs a live_test script against a throwaway container (see above)
- `build_inputs.py` — Parses Vue source to discover monitor form fields
- `build_models.py` — Extracts model definitions
- `build_monitor_types.py` — Discovers monitor type identifiers
- `build_notifications.py` — Discovers notification provider fields
- `build_notification_docstring.py` — Generates docstring entries for notification params
