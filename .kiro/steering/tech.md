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
       tests/test_status_page_incidents.py \
       tests/test_delete_id_coercion_v2.py \
       tests/test_monitor_cache_v2.py -v
```

Build + validate the package:

```
python -m build
python -m twine check dist/*
python scripts/check_sdist.py          # sdist contents; see the warning below
```

`check_sdist.py` asserts the sdist holds `tests/uptime_kuma_test_case.py` and
`CHANGELOG.md`, and allowlists everything else under `tests/` to `test_*.py` —
so `tests/.env`, `tests/.backups/**` and `tests/live_test_*.py` cannot reach a
published artifact. `publish.yml` runs it against `dist/*.tar.gz` between
`twine check` and `twine upload`, so a release is already gated on it; run it by
hand only when changing `MANIFEST.in`.

**A local `python -m build` is not trustworthy on its own here.**
`manifest_maker` reads an existing `*.egg-info/SOURCES.txt` back into the file
list, so a tree that built once with a broad `MANIFEST.in` pattern keeps
shipping those files after the pattern is reverted — reproduced at 111 members
including `tests/.env`. CI is immune (fresh checkout); this workstation is not.
`check_sdist.py` deletes the egg-info before building for exactly that reason.

Build docs locally:

```
pip install -r dev-requirements.txt
cd docs && make html   # docs/make.bat on Windows
```

## GitHub and external lookups

GitHub is interrogated with `gh` and `git`, **not** web search. Three
repositories are in play, and `-R` is always passed explicitly rather than
relying on the working directory:

| Repository | `-R` value | What it answers |
|---|---|---|
| This project | `pbarone/uptime-kuma-api2` | our issues, PRs, releases, CI runs |
| The original library | `lucasheld/uptime-kuma-api` | upstream triage, inherited issues and PRs |
| The Uptime Kuma server | `louislam/uptime-kuma` | server behavior — when a field, monitor type or event appeared |

For any question about **server** behavior — which version introduced a field, a
monitor type, an event — the authoritative source is Uptime Kuma's own source
and tags (`git log -S`, `git tag --contains`, `gh release view`), never a blog
post or secondary summary. A wrong answer here becomes a wrong version gate, and
a wrong version gate breaks v1.x.

Web search is for things genuinely outside these repositories: security advisory
details, PEP text, third-party library documentation. It is not how to answer a
question a repository can answer.

## Disposable test containers

This workstation has no Docker. Disposable Uptime Kuma containers run on a
separate host reached over SSH; its address and SSH user are recorded in the
**gitignored** root `.env` as `DOCKER-HOST` / `DOCKER-USER`. Read them from
there. They contain hyphens, so they are recorded values rather than consumable
shell variables.

**Never write that address, the SSH user, or any credential into a tracked
file.** It has been scrubbed from this repo's history once already and is
currently absent from it. Committed prose uses the `<docker-host>` and `<user>`
placeholders the existing specs use.

## Critical safety rule

**Never run the full `pytest tests/` against a real Uptime Kuma instance.** The
inherited integration tests delete every monitor, notification, proxy, tag,
status page, docker host, maintenance and API key on the target during setup.
Run only the unit files listed above unless you have a disposable instance.
