# Tech

## Stack

- **Language:** Python 3.8+ (tested 3.8–3.13; matches CI and PyPI classifiers)
- **Core dependency:** `python-socketio[client]` (the API is Socket.IO, not REST;
  a few endpoints like status-page fetch use `requests` over HTTP)
- **Version gating:** `packaging.version.parse` — the mechanism for supporting
  Uptime Kuma 1.x and 2.x from one codebase
- **Packaging:** `setup.py` (version single-sourced from
  `uptime_kuma_api/__version__.py`)
- **Docs:** Sphinx + autodoc, published on Read the Docs
  (`uptime-kuma-api2.readthedocs.io`), rebuilds on push to `main`
- **Tests:** `pytest`

## Version-gating idiom

Server-version-specific behavior is gated so v1.x connections stay correct:

```python
from packaging.version import parse as parse_version
if parse_version(self.version) >= parse_version("2.0"):
    ...  # v2-only fields
```

## Key commands

Unit tests (no live server — this is what CI runs):

```
pytest tests/test_monitor_types_v2.py tests/test_monitor_params_v2.py \
       tests/test_status_page_v2.py tests/test_notification_v2.py \
       tests/test_logger.py tests/test_monitor_builder.py \
       tests/test_status_page_incidents.py -v
```

Build + validate the package:

```
python -m build
python -m twine check dist/*
```

Build docs locally:

```
pip install -r dev-requirements.txt
cd docs && make html   # docs/make.bat on Windows
```

## Critical safety rule

**Never run the full `pytest tests/` against a real Uptime Kuma instance.** The
inherited integration tests delete every monitor, notification, proxy, tag,
status page, docker host, maintenance and API key on the target during setup.
Run only the unit files listed above unless you have a disposable instance.
