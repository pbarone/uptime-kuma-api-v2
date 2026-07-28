---
inclusion: manual
---

# Git workflow and releasing

Manually include this (`#git-and-releasing`) when committing, opening PRs, or
cutting a release.

## Commit messages — Conventional Commits

Every commit's first line follows
[Conventional Commits](https://www.conventionalcommits.org):

```
<type>: <short imperative summary>

<optional body: what and why, wrapped ~72 cols>

<optional footer>
```

**Types:** `feat` (new capability), `fix` (bug fix), `docs`, `test`, `ci`
(CI/build/release pipeline), `refactor`, `chore` (maintenance, no product
change).

**Breaking changes:** append `!` after the type and/or add a `BREAKING CHANGE:`
footer, e.g. `feat!: drop Python 3.7 support`.

The type maps to the semver bump (see below), so choose it honestly: a change
that only touches docs is `docs`, not `fix`. Bodies are encouraged for anything
non-trivial — explain the why, not just the what.

Enforcement tooling (commit linting, auto-changelog) is intentionally NOT set up
yet; the convention is followed by hand. Automated changelog/version tooling
(e.g. git-cliff, release-please) can be added later precisely because the
history is Conventional-Commit-clean.

## Branch and PR workflow

- **Never commit directly to `main`.** Work on a branch, open a PR, let CI run
  the full matrix, then merge.
- Branch names: `fix/...`, `feat/...`, `docs/...`, `ci/...`.
- Merge via PR (`--merge`) and delete the branch after.
- **Never force-push** or rewrite published history. Prefer new commits over
  amending anything already pushed.
- `gh` targets the wrong repo here because of the `upstream` remote — always
  pass `-R`: `-R pbarone/uptime-kuma-api2` for ours,
  `-R lucasheld/uptime-kuma-api` for upstream.

## CHANGELOG discipline

Every user-facing change gets a `CHANGELOG.md` entry under the release heading,
grouped (Features / Bugfixes / Documentation / Packaging / BREAKING CHANGES).
Bug entries state the symptom, cause, and fix. Credit incorporated PR authors by
handle. Docs/packaging-only releases say so explicitly.

## Versioning (semver)

Bump `uptime_kuma_api/__version__.py` — the single source of truth:

- `fix` / `docs` / `chore` → **patch** (2.2.1 → 2.2.2)
- `feat` → **minor** (2.2.x → 2.3.0)
- breaking change → **major** (2.x → 3.0.0), last resort (see the
  backward-compatibility policy in coding-standards)

## Release flow (proven on 2.2.1)

1. Land all changes on `main` via PR; confirm the full matrix is green.
2. Bump `__version__.py` and finalize the CHANGELOG entry (in the PR, not after).
3. Tag: `git tag -a vX.Y.Z -m "..."` — the tag **must** match `__version__`
   (the publish workflow enforces this and fails otherwise).
4. `git push origin vX.Y.Z` → the publish workflow runs: tests → tag/version
   check → `twine check` → upload to PyPI. A failure here is safe (it fails
   before uploading).
5. **Create the GitHub release manually** with both built artifacts attached —
   the workflow does not create it. Use the CHANGELOG entry as the notes.
6. Verify on PyPI via the **version-specific** endpoint
   (`https://pypi.org/pypi/uptime-kuma-api2/X.Y.Z/json`); the index/simple API
   is CDN-cached and lags a few minutes.
7. Read the Docs rebuilds on the push automatically.

## Publishing is irreversible

A PyPI version number is burned permanently and a filename can never be
re-uploaded. Get explicit confirmation before pushing a release tag, and never
tag a red `main`.

## Secrets

Never commit `tests/.env`, `tests/.backups/`, or credentials. The
`PYPI_API_TOKEN` lives in GitHub Actions secrets only. Flag any file that looks
like it contains a token or password before staging it.
