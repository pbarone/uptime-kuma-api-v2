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

That list is deliberately short, and adding to it is a real cost: this library
is itself a transitive dependency of other people's automation (the Ansible
collection among them), so every runtime dependency we take, they take. Solve it
with the standard library or an already-installed package first; a new runtime
dependency needs a reason beyond convenience.

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
pytest -v
```

That is the whole command, and it is the same one `test.yml` and `publish.yml`
run. The nine-filename list this block used to carry is gone from all seven
places that held a copy: `tests/conftest.py` marks a test `integration` when its
class extends `UptimeKumaTestCase`, and `pytest.ini` deselects that marker by
default. Do **not** reintroduce a file list — deriving it from the base class is
the point, and a tenth test file should require no edit here.

An empty collection exits 5, so a broken selection fails loudly rather than
passing green having run nothing.

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

**A local `python -m build` can inherit stale state.** `manifest_maker.run`
calls `add_defaults()` — which reads an existing `*.egg-info/SOURCES.txt` back
into the file list — *before* `read_template()` processes `MANIFEST.in`. So a
tree that built once with a broad pattern keeps shipping those files after the
pattern is reverted: reproduced at 111 members including `tests/.env`. CI is
immune (fresh checkout); this workstation is not. Two things contain it, and the
distinction matters:

- The `global-exclude` / `prune` lines in `MANIFEST.in` run *after* that
  read-back and strip it, so **no credential can reach an sdist by this route** —
  the same poisoned tree drops from 111 members to 61 with zero credentials.
  They are load-bearing, not decorative. The five `no previously-included files
  matching` warnings on a clean build are the healthy state; do not delete the
  patterns to silence them. Their one limit: `MANIFEST.in` applies in file order,
  so a broad include appended *below* them defeats them.
- `check_sdist.py` deletes the egg-info before building, and its allowlist
  rejects any residue regardless of route.

If a local build looks wrong, delete `*.egg-info` and rebuild before debugging
anything else.

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

**Never run `pytest -m integration` against a real Uptime Kuma instance.** The
inherited integration tests delete every monitor, notification, proxy, tag,
status page, docker host, maintenance and API key on the target during setup.

The shape of this rule changed once the marker landed, and the change is worth
being precise about rather than trusting muscle memory. It used to read "never
run the full `pytest tests/`", because bare `pytest` collected the destructive
tests and the only protection was remembering to name the nine unit files.
`pytest.ini` now deselects the `integration` marker by default, so **bare
`pytest` is safe** and the dangerous invocation is the explicit opt-in above.

That closes the accident but not the deliberate mistake: `-m integration`,
`-m ""` and `unittest discover` all still reach every destructive test. Use
`./run_tests.sh`, which creates and destroys its own containers per server
version, or a disposable instance you are willing to lose.
