# Contributing

Thanks for considering a contribution to `uptime-kuma-api2`. This is a
maintained continuation of [`lucasheld/uptime-kuma-api`](https://github.com/lucasheld/uptime-kuma-api)
under the original MIT license.

## Project shape

- **Import package:** `uptime_kuma_api` (never renamed — existing user code
  depends on it). **PyPI name:** `uptime-kuma-api2`.
- Supports Uptime Kuma **1.21.3+ through 2.x from one codebase**. Server-
  version-specific behavior is gated behind `parse_version(self.version)`
  checks. The lowest gate in the code is `1.22`, so servers below that
  deliberately take the pre-1.22 payload path; 1.21.3 is the declared support
  floor, not the lowest branch.
- **Backward compatibility with v1.x is not negotiable.** A change that breaks
  a v1.x connection is a regression.

## Development setup

```
python -m venv .venv
.venv/Scripts/activate        # Windows;  source .venv/bin/activate elsewhere
pip install -e .
pip install pytest
pip install -r dev-requirements.txt   # only needed to build docs
```

## Running tests

Run the unit suite — no server required, this is what CI runs:

```
pytest tests/test_monitor_types_v2.py tests/test_monitor_params_v2.py \
       tests/test_status_page_v2.py tests/test_notification_v2.py \
       tests/test_logger.py tests/test_monitor_builder.py \
       tests/test_status_page_incidents.py \
       tests/test_delete_id_coercion_v2.py \
       tests/test_monitor_cache_v2.py -v
```

> **Do not run the full `pytest tests/`** against an Uptime Kuma instance you
> care about. The inherited integration tests delete **all** data (monitors,
> notifications, proxies, tags, status pages, docker hosts, maintenances, API
> keys) on the target during setup. They are meant for a disposable instance
> (e.g. a throwaway Docker container).

## What we look for in a change

- **Reproduce before fixing.** Issue titles here often misdescribe the real
  defect — confirm the actual cause in the code first.
- **Every bug fix ships with a regression test** that is proven to fail against
  the unfixed code (revert the fix, watch it go red, restore).
- **Additive over breaking.** Prefer new optional parameters and new return
  keys over changing existing signatures or return shapes. When a server
  renames a field across versions, return both keys where feasible.
- **Keep the public API in sync:** export new public classes in `__init__.py`,
  add them to `docs/api.rst` (Sphinx autodoc won't include them otherwise), add
  a `MonitorBuilder` setter for new monitor fields, and add a `CHANGELOG.md`
  entry.

## Commit messages — Conventional Commits

First line: `<type>: <summary>`. Types: `feat`, `fix`, `docs`, `test`, `ci`,
`refactor`, `chore`. Breaking changes use `!` (e.g. `feat!: drop Python 3.7`).
The type guides the version bump (fix → patch, feat → minor, breaking → major).

## Pull requests

1. Work on a branch (`fix/...`, `feat/...`, `docs/...`), never commit to `main`.
2. Open a PR against `main`; CI runs the full Python 3.8–3.13 matrix.
3. Fill in the PR checklist (tests, changelog, backward-compat, docs).
4. A maintainer merges after review.

## A note on AI-agent steering files

This repo commits AI-agent guidance under `.kiro/steering/`. Because those
files instruct coding agents, changes to them are reviewed with the same care
as code — treat a PR that edits steering as a code change, not a docs tweak.

## Reporting bugs and requesting features

Use the issue templates. For bugs, the Uptime Kuma **server version**, the
**library version**, and your **Python version** are required — most triage
time is lost without them.

## Security

Do not report security issues in public issues. See [SECURITY.md](SECURITY.md).
