<!-- Keep the PR title in Conventional Commits form, e.g. "fix: ...", "feat: ...", "docs: ...". -->

## What and why

<!-- Briefly: what does this change, and why? Link any related issue (Fixes #NN). -->

## Checklist

- [ ] Title follows Conventional Commits (`fix:` / `feat:` / `docs:` / `test:` / `ci:` / `refactor:` / `chore:`; `!` for breaking)
- [ ] Tests pass: the v2 unit suite runs clean (see CONTRIBUTING)
- [ ] Bug fixes include a regression test **proven to fail against the unfixed code**
- [ ] Backward compatibility with Uptime Kuma v1.x is preserved (version-gated where needed)
- [ ] Public API changes are additive; new public classes are exported in `__init__.py` **and** added to `docs/api.rst`
- [ ] `CHANGELOG.md` updated for any user-facing change
- [ ] No secrets, tokens, or real credentials in the diff

## Notes for the reviewer

<!-- Anything that needs a live server to verify, tradeoffs, follow-ups, etc. -->
