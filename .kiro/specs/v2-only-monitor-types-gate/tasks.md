# Implementation Plan

**The policy question is settled by evidence, not by preference — see
`design.md` `## Policy collision`.** The conditions spec's objection to raising
was conditional on failure being *unverified*; `pre-fix-evidence.md` verifies it,
so the objection is discharged rather than overridden. Do not reopen it, and do
not "restore consistency" by deleting the guard: on a 1.x server there is no
working path for these four types to preserve.

**Sequencing is settled.** #12 ships alone, ahead of
[#14](https://github.com/pbarone/uptime-kuma-api2/issues/14), which gets its own
requirements/design spec later — it is a policy deliverable, not a bugfix. The
signalling here (`UptimeKumaException`) is **provisional** and #14 may narrow it;
because a subclass of `UptimeKumaException` keeps every existing catcher working
(as `Timeout` already demonstrates), that later narrowing is additive.

- [x] 1. Add the private type set and the guard to `uptime_kuma_api/api.py`
  - Module-level `_V2_ONLY_MONITOR_TYPES` frozenset of the four `MonitorType`
    members, with the comment pointing at `pre-fix-evidence.md` for provenance
  - `_check_monitor_type_supported(self, type_)` immediately after
    `_check_conditions_supported`, gating on `self._parsed_version() <
    parse_version("2.0")` like every other gate
  - Message must name the type's **string value**, `2.0`, and `self.version`.
    Use `MonitorType(type_).value`, not bare interpolation — str-Enum
    `__format__` differs across Python 3.8-3.13
  - Sphinx-style docstring with `:param:` and `:raises:`, per coding standards.
    Private, so it does not reach the API reference, but the format is the
    house style and `_check_conditions_supported` sets the precedent
  - Nothing is exported from `__init__.py` and nothing is added to
    `docs/api.rst` — requirement 3.5
  - _Requirements: 2.1, 2.2, 3.5, 3.7_

- [x] 2. Wire the two call sites
  - `_build_monitor_data`: `self._check_monitor_type_supported(type)`
    immediately **after** `self._check_conditions_supported(conditions)`. The
    order is load-bearing — a call tripping both guards must raise the message
    it raises today (requirement 3.3)
  - `edit_monitor`: `self._check_monitor_type_supported(kwargs.get("type"))`
    beside the existing conditions guard. `kwargs.get("type")`, **not** the
    merged `data["type"]` — the guard fires on what the caller explicitly asked
    for, so an unrelated `edit_monitor(id_, interval=120)` on an existing
    monitor of one of these types cannot raise spuriously
  - Leave `_check_arguments_monitor`'s `required_args_by_type` entries alone
    (requirement 3.4)
  - _Requirements: 2.1, 2.3, 3.3, 3.4_

- [x] 3. Prove the bug condition is real, then write `TestV2OnlyMonitorTypesV1Gate`
  - **Run the new tests against the unfixed code first** and record that they
    fail (stash the change from tasks 1-2, or write the tests before wiring the
    call sites). A test that has only ever passed proves nothing — `testing.md`
  - In `tests/test_monitor_params_v2.py`, after the existing conditions-gate
    classes. **Do not create a new test file**: the nine-file CI list is
    duplicated across `CONTRIBUTING.md`, `AGENTS.md`,
    `.github/workflows/test.yml`, `run_tests.sh` and the steering files
  - Follow the file's `_v1_api()` idiom — `MagicMock(spec=UptimeKumaApi)` with
    the real `_parsed_version` and the real guards bound on, so the gate parses
    `self.version` for real rather than hitting a stub
  - Cases: each of the four types raises on v1 through `_build_monitor_data`
    (`subTest` per type, with that type's required companion arguments);
    the message names the type string, `2.0` and the observed version;
    `edit_monitor(7, type=...)` raises with `get_monitor` and `_call` both
    asserted not called; a `MonitorBuilder` config raises at the `add_monitor`
    boundary; a bare `"snmp"` string is gated identically to the enum member
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 4. Write `TestV2OnlyMonitorTypesPreservation`
  - All four types accepted on `2.4.0` with companion fields present and
    unchanged in the payload — the executable form of requirement 3.1
  - A representative set of non-v2-only types (HTTP, PING, PORT, DNS, PUSH)
    raises nothing on v1 and produces an unchanged payload (3.2)
  - `add_monitor(type=SNMP, conditions=[...])` on v1 raises the **conditions**
    message, not the type message — pins the guard order (3.3)
  - An unparseable version (`2.0.0-dev-nightly-20240101`, the string
    `_parsed_version` already handles) permits all four types (3.7)
  - `MonitorType` still exposes all four members with their existing string
    values, so the enum is provably untouched
  - Assert the absence of a raise **explicitly** where that is the contract, so
    a future over-broad gate fails a test rather than passing unnoticed
  - _Requirements: 3.1, 3.2, 3.3, 3.5, 3.7_

- [x] 5. Run the CI unit suite and confirm green
  - The nine v2 unit files named in `CONTRIBUTING.md`, explicitly. **Never bare
    `pytest tests/`** — the inherited integration tests wipe every monitor,
    notification, proxy, tag, status page, docker host, maintenance and API key
    on whatever instance they reach
  - Confirm no pre-existing test changed behaviour, in particular the conditions
    gate classes and `test_monitor_cache_v2.py`
  - _Requirements: 2.5, 3.1, 3.2, 3.3, 3.6_

- [x] 6. CHANGELOG, and retire the note that contradicts this fix
  - Add a `#### Bugfixes` entry under the **existing** `### Unreleased` heading.
    Do not reopen the 2.3.0 section
  - State the symptom in both directions (opaque `SQLITE_ERROR` today; silently
    `PENDING` once fields are gated), the cause, the fix, and that no public
    surface was added
  - **Retire the 2.3.0 deferral note.** `### Release 2.3.0` → `#### Notes` →
    "Two follow-ups are noted here and designed nowhere", item (2), currently
    reads that the four types are "Out of scope here, and it fails loudly rather
    than silently, which is why it is a note and not a fix." Leaving that would
    contradict the fix *and* leave the corrected mechanism on record wrong.
    Rewrite item (2) to record that it was fixed under `### Unreleased`, keeping
    2.3.0's history honest rather than deleting the note
  - Item (1) of that same note — the uniform "dropped v2-only field" signal — is
    #14 and stays as it is
  - _Requirements: 2.5, 2.6_

- [x] 7. Annotate the narrowed earlier assertion
  - Checked, per the conditions spec's "recording such narrowing is a
    first-class deliverable, not a footnote":
    - **`uptime-kuma-v2-support-backlog/requirements.md` requirement 13.3** —
      needs **no substantive narrowing**. It governs v2-only monitor
      *parameters*; `type` is a parameter every monitor has, whose *value* is
      v2-only, so a monitor type is outside its scope. Its existing `NARROWED`
      block already carries the field-level rule. Add only a one-line pointer to
      this spec, because a contributor scanning 13.3 for "the rule for v2-only
      things" will land there and must not conclude types are dropped silently
    - **`uptime-kuma-v2-support-backlog/requirements.md` requirement 1.7** — this
      is the assertion that actually narrows. It reads "WHEN any new monitor type
      is created with all required fields populated, THE Library SHALL return a
      response containing `"msg": "Added Successfully."`", unconditionally. That
      is now true only for servers >= 2.0. Annotate in place, in the same
      `> **NARROWED by ...**` style 13.3 already uses
  - _Requirements: 2.6_

- [ ] 8. Branch, commit, PR — confirm with the user before pushing
  - Branch `fix/v2-only-monitor-types-gate` off `main`. Never commit to `main`:
    the `protect-main` ruleset rejects it outright, with no admin bypass
  - Conventional Commits. Body explains *why* — including that #12's premise was
    corrected by the evidence run
  - Verify `tests/.env` and the Docker host address appear in nothing staged.
    `pre-fix-evidence.md` is tracked and uses the `<docker-host>` placeholder;
    confirm that before staging it
  - **Get explicit confirmation before `git push`.** Open the PR into `main`,
    let the six-job matrix run, then merge with `--merge`
  - No version bump and no release tag in this spec: `### Unreleased` accumulates
    until a release is cut deliberately

- [x] 9. Destroy the disposable v1 container
  - `docker rm -f kuma-v1-mtypes` on the Docker host. It ran without a volume,
    so removing it destroys all state
