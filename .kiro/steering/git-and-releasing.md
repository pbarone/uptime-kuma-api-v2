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
- Branch names: `<type>/<short-description>`, where `<type>` is the
  Conventional Commit type of the change's dominant purpose — so any type from
  the **Types** list above is valid (`feat`, `fix`, `docs`, `test`, `ci`,
  `refactor`, `chore`), e.g. `chore/bump-jinja2-3-1-6`. Stated as a rule rather
  than a fixed list of prefixes on purpose: a second enumerated list here would
  duplicate the Types list and drift from it, which is the same failure mode as
  the status-check coupling described below.
- Merge via PR (`--merge`) and delete the branch after.
- **Never force-push** or rewrite published history. Prefer new commits over
  amending anything already pushed.
- **Rewriting *unpushed* history is safe** and needs no force-push — but verify
  that before rewriting, don't assume it. `git merge-base --is-ancestor
  origin/<branch> HEAD` must exit 0: that proves the remote tip is still an
  ancestor of yours, so a plain `git push` fast-forwards. Take a
  `backup/<name>` ref first so the pre-rewrite commits stay reachable. Note the
  catch for content scrubs: while that backup ref exists, `git log --all
  -S"<string>"` still finds the old content, so the scrub is not complete until
  the backup is deleted.
- The `upstream` remote that used to make `gh` target lucasheld's repo was
  removed (2026-07-30), but keep passing `-R` anyway:
  `-R pbarone/uptime-kuma-api2` for ours, `-R lucasheld/uptime-kuma-api` for
  upstream.

**Merge method: merge commits (`--merge`).** Squash and rebase are not used. The
per-commit reasoning on a branch is worth keeping — the bodies explain why each
step was taken — and `git log --first-parent main` still gives the clean
release-level view when that's what you want. Honest caveat: the `protect-main`
ruleset currently still *permits* squash and rebase, so this is convention, not
enforcement. Narrowing **Allowed merge methods** to merge-only is a recommended
follow-up, so the setting matches the documented policy.

## Branch protection — the conventions are enforced now

Two rulesets exist, both with **empty bypass lists** and
`current_user_can_bypass: never`. There is no admin override: a direct push to
`main` is *rejected*, not merely against convention.

`protect-main` targets the default branch with `pull_request` (0 required
approvals), `required_status_checks`, `deletion` and `non_fast_forward`.
`protect-release-tags` is covered under "Publishing is irreversible" below.

If CI is ever broken for reasons unrelated to the change you need to land, the
escape hatch is to set the ruleset's **Enforcement** to Disabled temporarily and
re-enable it right after — a deliberate, logged act. Do **not** add a bypass
actor instead: with a single maintainer, that permanently disables the
protection rather than suspending it once.

### The drift coupling to watch

`protect-main` requires six status checks **by literal name**: `full (3.8)`,
`full (3.9)`, `full (3.10)`, `full (3.11)`, `full (3.12)`, `full (3.13)`. These
must stay in sync with the Python matrix in `.github/workflows/test.yml`. Change
one without the other and the failure is silent, in one of two directions:

- A required check that never reports (version dropped from the matrix, still
  required) blocks **every** merge, forever, with nothing to fix in the code.
- A new matrix version that isn't in the required list silently stops gating —
  merges pass while that version is untested.

**Never add `quick (3.11)` as a required check.** It is deliberately skipped on
`pull_request` events, so requiring it would deadlock every merge.

This is the same class of drift as the explicit unit-test file list, which has
bitten this project repeatedly: two places encode the same fact, and only one
gets updated. Treat a matrix edit as a two-file change.

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

**The tag is irreversible too, and earlier than PyPI.** The
`protect-release-tags` ruleset targets `refs/tags/v*` with `update`, `deletion`
and `non_fast_forward` rules and an empty bypass list. So a release tag cannot be
moved or deleted from the moment it lands — before the PyPI upload, not after
it. `git tag -d` plus a re-push is no longer a fix for a mistagged commit; the
only recovery is burning the next patch version on a corrected tag.

That moves the point of no return earlier and raises the stakes on the pre-tag
checks. Before `git push origin vX.Y.Z`, confirm both:

- `__version__.py` matches the tag you are about to push, exactly.
- `main` is green — the full matrix, on the commit you are tagging.

## Secrets

Never commit `tests/.env`, `tests/.backups/`, or credentials. The
`PYPI_API_TOKEN` lives in GitHub Actions secrets only. Flag any file that looks
like it contains a token or password before staging it.
