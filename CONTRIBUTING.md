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
pytest -v
```

That is the whole command. There is no list of test files to keep in step:
`tests/conftest.py` marks a test `integration` when its class extends
`UptimeKumaTestCase` — the base class whose `setUp` connects to a server and
deletes everything on it — and `pytest.ini` deselects that marker by default.
Adding a test file therefore needs no change here, in the workflows, or in the
README. A new unit test runs because it does not extend that base class; a new
integration test is excluded because it does.

> **The integration tests delete all data on the instance they reach** —
> monitors, notifications, proxies, tags, status pages, docker hosts,
> maintenances and API keys — during setup. They are meant for a disposable
> instance such as a throwaway Docker container, never one you care about.
>
> A bare `pytest` no longer runs them, so the old footgun is closed by default.
> Running them is deliberate and explicit:
>
> ```
> pytest -m integration        # DESTRUCTIVE
> ```
>
> `./run_tests.sh` is the maintained way to do it safely: it creates and
> destroys its own containers per server version. It drives the tests through
> `unittest discover`, which ignores pytest markers, so it runs the full suite
> regardless of the default above.

### Live verification (optional, maintainer-scoped)

**A contribution does not need this.** The unit suite above requires no
configuration and is the whole of what CI runs.

Separately, `tests/live_test_*.py` are manual scripts that check round-trip
behaviour against a real Uptime Kuma instance. They are `live_test_`-prefixed so
pytest never collects them. They read their configuration from `tests/.env`:

```
cp tests/.env.example tests/.env    # then fill in your own values
```

`tests/.env.example` lists every key, which script consumes it, and what each is
for. `tests/.env` is gitignored and must stay that way.

These scripts **create and delete data** on whatever you point them at —
`live_test_cleanup.py` deletes monitors, notifications and status pages — so use
a disposable instance you own, and always run `live_test_cleanup.py --dry-run`
before the real thing.

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

1. Work on a branch named `<type>/<short-description>`, where `<type>` is the
   Conventional Commit type of the change's main purpose (so any of the types
   listed above — e.g. `fix/...`, `docs/...`, `chore/...`). Never commit to
   `main`.
2. Open a PR against `main`; CI runs the full Python 3.8–3.13 matrix.
3. Fill in the PR checklist (tests, changelog, backward-compat, docs).
4. A maintainer merges after review.

`main` is branch-protected, so steps 1 and 2 are enforced rather than merely
asked for: a direct push is rejected, a pull request is required, and the full
Python 3.8–3.13 matrix must report green before the merge button unlocks.

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
