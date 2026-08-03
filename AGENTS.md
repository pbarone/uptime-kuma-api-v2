# AGENTS.md

Guidance for AI coding agents working in this repository. (Kiro users: the
authoritative, richer guidance is in `.kiro/steering/`; this file mirrors the
essentials for other tools.)

## What this is

`uptime-kuma-api2` — a Python wrapper for the Uptime Kuma Socket.IO API. A
maintained continuation of `lucasheld/uptime-kuma-api` under the original MIT
license. **Import package:** `uptime_kuma_api` (never rename it). **PyPI name:**
`uptime-kuma-api2`.

## Non-negotiables

- **Backward compatibility with Uptime Kuma v1.x is sacred.** The library
  supports 1.21.3+ through 2.x from one codebase; gate server-version-specific
  behavior behind `parse_version(self.version)`. (The lowest gate in the code is
  `1.22`, so sub-1.22 servers take the pre-1.22 payload path — 1.21.3 is the
  declared support floor, not the lowest branch.)
- **Never run `pytest tests/` (bare) against a real Uptime Kuma instance** — the
  inherited integration tests delete all of its data. Run only the v2 unit
  files (see CONTRIBUTING.md).
- **Don't add public API surface casually.** New parameters are additive and
  optional; new public classes must be exported in `__init__.py` and added to
  `docs/api.rst`.

## Working conventions

- Reproduce a bug in the code before fixing it; issue titles often misdescribe
  the real defect.
- Every bug fix gets a regression test proven to fail against the unfixed code.
- Conventional Commits for messages (`fix:`, `feat:`, `docs:`, ...); `!` for
  breaking changes.
- Branch → PR → CI → merge; never commit to `main` directly; never force-push.
- Update `CHANGELOG.md` for user-facing changes.

## Commands

Unit tests (what CI runs):

```
pytest tests/test_monitor_types_v2.py tests/test_monitor_params_v2.py \
       tests/test_status_page_v2.py tests/test_notification_v2.py \
       tests/test_logger.py tests/test_monitor_builder.py \
       tests/test_status_page_incidents.py \
       tests/test_delete_id_coercion_v2.py \
       tests/test_monitor_cache_v2.py -v
```

See `CONTRIBUTING.md` for full setup and `.kiro/steering/` for detailed
standards.
