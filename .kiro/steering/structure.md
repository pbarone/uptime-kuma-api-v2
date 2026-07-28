# Structure

## Layout

```
uptime_kuma_api/            # the package (import name)
  api.py                    # UptimeKumaApi — the large core; most logic lives here
  monitor_builder.py        # MonitorBuilder fluent builder
  notification_providers.py # provider option/metadata tables
  monitor_type.py, auth_method.py, ...  # enums
  __version__.py            # single source of the version number
  __init__.py               # public exports — anything here is public API
tests/                      # see taxonomy below
docs/                       # Sphinx: conf.py, api.rst (autodoc), index.rst, install.rst
scripts/                    # code-generation helpers (build_*.py); not shipped runtime
setup.py, CHANGELOG.md, README.md, .readthedocs.yaml
UPSTREAM_TRIAGE.md          # local-only working notes (gitignored)
```

## tests/ taxonomy — know which is which

- **v2 unit tests** (`test_monitor_types_v2.py`, `test_monitor_params_v2.py`,
  `test_status_page_v2.py`, `test_notification_v2.py`, `test_logger.py`,
  `test_monitor_builder.py`, `test_status_page_incidents.py`): no live server,
  mock the version/transport. **This is the CI suite.** Add regression tests here.
- **Inherited integration tests** (`test_monitor.py`, `test_notification.py`,
  `test_status_page.py`, and the rest via `uptime_kuma_test_case.py`): require a
  live instance at `127.0.0.1:3001` and **wipe all its data** on setup. Not run
  in CI. Never point them at anything you care about.
- **Live scripts** (`live_test_backup.py`, `live_test_create.py`,
  `live_test_cleanup.py`): manual round-trip verification against a real 2.x
  instance, driven by `tests/.env`. Not tests, not run by CI.

## Where changes usually go

- New monitor type / parameter → `_build_monitor_data` and validation in
  `api.py`, the enum in `monitor_type.py`, a matching `MonitorBuilder` setter,
  a v2 unit test, and `docs/api.rst` if a new public class.
- New notification provider → `notification_providers.py` tables + a v2 test.
- New public class/function → export in `__init__.py` **and** add to
  `docs/api.rst` (autodoc won't include it otherwise).

## Never commit

`tests/.env`, `tests/.backups/`, `tests/.live_test_ids.json`, and
`UPSTREAM_TRIAGE.md` are gitignored and hold secrets or transient state.
