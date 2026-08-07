# Implementation Plan

Prerequisite, already satisfied: **issue #30** (the Version_Comparison_Fix) landed
in `dcfb3d4`, merged via PR #31. Verified before this plan was written —
`_parsed_version()` now compares `base_version` and catches `TypeError`,
`2.0.0-beta.4` gates as 2.0, `1.23.0-beta.1` as 1.23, `2.1.0-beta.1` as 2.1,
`1.21.3` still below 1.22, and the unit suite is green at 237 passed / 1225
subtests. Requirement 5.7 is discharged.

Task order follows `## Sequencing` in `requirements.md`: the Verification_Run
comes first because its results can shrink the Field_Registry, and building the
registry before pruning it would ship a warning about a field the server would
have accepted (requirements 7.2, 7.3).

One deliberate ordering note. Tasks 4 and 5 land the warning category and the
registry data **before** the tests, because a test that asserts
`UnsupportedFieldWarning` is emitted cannot import until the class exists, and an
`ImportError`-red is weaker evidence than an assertion-red. Both are inert on
their own — no behaviour changes until task 7 wires the pass in — so the red run
in task 9 still executes against code that withholds silently, which is the
condition the properties are red against.

---

## Phase 1 — Verification_Run (requirement 7), before any registry is built

- [x] 1. Write the v1 verification script
  - New `tests/live_test_v2_only_fields_v1.py`, modelled on the existing
    `tests/live_test_conditions_v1.py` and sharing its safety posture
  - Read its own `UPTIME_KUMA_V1_URL` / `UPTIME_KUMA_V1_USERNAME` /
    `UPTIME_KUMA_V1_PASSWORD` keys, **not** the 2.x `tests/.env` keys, with no
    default URL, so it cannot be pointed at the 2.x instance by omission
  - Abort before sending any monitor payload unless the reported version begins
    with `1.23`; on an unset URL or a non-1.23 server, create nothing and exit
    reporting `FAIL` naming the unconfirmed target
  - For each of the 25 Reachable_On_V1 fields: create a monitor of a type the
    field applies to with that field on the wire, read it back, compare sent
    against returned, and record exactly one of `REJECTED`, `ACCEPTED`, `ABSENT`,
    `MISMATCH` together with the monitor type used
  - Delete every created monitor in a `finally` block, including on the path
    where sending or reading back raised
  - ASCII output only — `PASS` / `FAIL` / `->`, no check marks or box-drawing
  - Do not add it to CI, and do not append it to the 2.x backup → create →
    cleanup cycle; it is a standalone one-off
  - _Requirements: 7.1, 7.4, 7.5, 7.6, 7.7, 7.8_

- [x] 2. Run it against a disposable 1.23.x container and record the results
  - **Manual step, needs the Docker host over SSH** — this workstation has no
    Docker. Read `DOCKER-HOST` / `DOCKER-USER` from the gitignored root `.env`;
    never write either into a tracked file
  - Start a throwaway container on a free port, run the script, then
    `docker rm -f` it
  - Record per-field verdicts in
    `.kiro/specs/v2-only-fields-rule/v1-verification-results.md` with the
    observed version, the run date, and `NOT_OBSERVED` for any of the 25 not
    exercised, so an incomplete run reads as incomplete
  - Refer to the host, the SSH user and any credential only as `<docker-host>`
    and `<user>`
  - _Requirements: 7.1, 7.9, 7.10_

- [x] 3. Check how the companion Ansible collection handles unexpected stderr
  - `warnings.warn` writes to stderr via `warnings.showwarning`, and the
    collection wraps these calls in a module process
  - Record the observed behaviour in the same results file, beside the verdict
    table, so a reader sees the carrier decision next to the evidence
  - If warnings break module output parsing, the ratified fallback is `logging`:
    swap the carrier, drop requirements 2.10 and 8.7 (filterability is lost), and
    change nothing else. Note the wrinkle already recorded in the design —
    `logging.lastResort` also emits WARNING and above to stderr when no handler
    is configured, so the fallback is quieter only for a caller who configures
    logging
  - Must complete before task 12 merges, because swapping carriers after a public
    name has shipped would itself be a breaking change
  - _Requirements: 7.11_

---

## Phase 2 — the inert pieces

- [x] 4. Add the `UnsupportedFieldWarning` category
  - `class UnsupportedFieldWarning(UserWarning)` in
    `uptime_kuma_api/exceptions.py`, beside `UptimeKumaException` and `Timeout`
  - `UserWarning`, not `RuntimeWarning` (this reports something the *caller* did)
    and not `DeprecationWarning` (filtered out by default outside `__main__`,
    which would hide the Signal from exactly the callers who need it, and nothing
    here is deprecated)
  - Docstring must state plainly that `except UptimeKumaException` does **not**
    catch it — the class lives in `exceptions.py`, so the opposite assumption is
    reasonable
  - Export from `uptime_kuma_api/__init__.py` and add
    `.. autoexception:: UnsupportedFieldWarning` to the `Exceptions` section of
    `docs/api.rst`. Autodoc has no discovery mechanism and emits no warning for
    an omitted export, so the docs half cannot be deferred
  - This is the change's **only** new public name
  - _Requirements: 2.9, 6.9, 6.10_

- [x] 5. Add the Field_Registry data
  - `from collections import namedtuple` and
    `_FieldRule = namedtuple("_FieldRule", ("floor", "types", "behaviour"))` at
    module scope in `api.py`, beside `_V2_ONLY_MONITOR_TYPES`
  - `_WITHHOLD` / `_RAISE` string constants, compared with `==` not `is`
  - `_V2_ONLY_MONITOR_FIELDS` dict: `conditions` with `_RAISE`, the other 25 with
    `_WITHHOLD`, each carrying its floor as a **string** (`"2.0"`) and its type
    set as a `frozenset` — or `None` for unrestricted, emphatically **not** an
    empty `frozenset`, which would silently omit the field everywhere
  - Reuse the 14-type `ipFamily` list and the 4-type HTTP list as named
    frozensets rather than repeating them
  - Declaration order is the order withheld fields appear in the warning message
    and must stay stable; the comment must say so
  - Prune any field the task 2 results marked `ACCEPTED` — removal is the whole
    edit, and the field then reaches the payload unconditionally
  - _Requirements: 4.1, 4.3, 4.4, 4.6, 4.8, 7.2_

- [x] 6. Add the two private helpers
  - `_withheld_v2_fields(self, supplied, type_=None) -> list[str]` — iterate the
    registry in declaration order, skip `_RAISE` entries, skip entries whose type
    set excludes `type_`, skip entries whose type set is non-`None` when `type_`
    is `None`, and return the names whose supplied value is not `None` and whose
    floor is above `self._parsed_version()`
  - `_warn_withheld_v2_fields(self, withheld, stacklevel) -> None` — emit exactly
    one `warnings.warn` of `UnsupportedFieldWarning` naming every withheld field
    with its floor and the Server_Version the `version` property reports, and
    return without warning on an empty list
  - `stacklevel` is a parameter, not a constant: 4 from `_build_monitor_data`
    (helper → builder → `add_monitor` → caller), 3 from `edit_monitor`
  - Sphinx-style docstrings with `:param:` / `:return:` / `:raises:`, per house
    style; private, so they do not reach the API reference
  - _Requirements: 2.1, 2.2, 2.3, 4.9_

---

## Phase 3 — tests, confirmed red before the pass is wired

- [x] 7. Write the four new test classes in `tests/test_monitor_params_v2.py`
  - **No new test file.** Add classes only; do not edit any existing class
  - `TestV2OnlyFieldsWithheld` — properties 1, 2, 4. Parametrise over the
    registry rather than hand-picking, so a future entry is covered on arrival;
    at least one field from each of the five groups in the requirements table,
    `snmp_v3_username` excluded as not Reachable_On_V1
  - `TestV2OnlyFieldsSignal` — properties 3, 6, and the two
    `simplefilter("error", UnsupportedFieldWarning)` cases. **Every** test wraps
    the call in `warnings.catch_warnings()` with `simplefilter("always")`, or the
    default `(message, category, module, lineno)` dedup makes it vacuous. One
    test asserts `w[0].filename` is the test module rather than `api.py` — that
    is the only thing that catches a wrong `stacklevel`
  - `TestV2OnlyFieldsEditPath` — property 10, plus that `get_monitor` is never
    reached when the escalated warning raises
  - `TestV2OnlyFieldsPreservation` — properties 5, 7, 8, 9; the registry-privacy
    assertions mirroring the existing `_V2_ONLY_MONITOR_TYPES` test;
    `issubclass(UnsupportedFieldWarning, UserWarning)`; `inspect.signature`
    equality for `add_monitor` / `edit_monitor`; and the one-new-public-name set
    difference
  - Bind the real `_parsed_version`, `_check_conditions_supported`,
    `_check_monitor_type_supported`, `_withheld_v2_fields`,
    `_warn_withheld_v2_fields` and `_build_monitor_data` onto a
    `MagicMock(spec=UptimeKumaApi)`. A spec'd mock stubs out anything not bound,
    so an unbound guard never runs and the test passes vacuously
  - Two generator obligations: falsy-but-not-`None` values (`saveResponse=False`,
    `cacheBust=False`, `responsecheck=""`, `screenshot_delay=0`) must be in the
    corpus, and **not** `responseMaxLength=0`, which the preamble `ValueError`
    rejects before the pass runs; and versions either side of `2.0` plus exactly
    at it, reusing `CANONICAL_VALID_VERSIONS`
  - Seeded `PBT_SEED` / `PBT_CASES` idiom, not `hypothesis`. ASCII output only
  - Leave `TestValidVersionGatePreservation` and
    `TestUnparseableVersionBugCondition` unmodified
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.9, 8.10, 8.12_

- [x] 8. Confirm the red run and record it
  - Run `pytest -v` with tasks 4-6 in place but the pass not yet wired
  - Expect properties 1-4, 6 and 10 to fail: today's code withholds silently, so
    every warning assertion has nothing to catch, and `edit_monitor` merges a
    below-floor field straight through
  - Expect properties 5, 7, 8 and 9 to pass — they are preservation, and that is
    what they are for
  - Record the failure count in the PR description. Per `testing.md`, a property
    that has only ever passed is not evidence
  - _Requirements: 8.11_

---

## Phase 4 — wire the pass in

- [x] 9. Replace the `>= 2.0` block and the seven in-place gates in `_build_monitor_data`
  - Keep `conditions`' own emission line — the caller's list must reach the
    payload as the same object and `None` must become `[]`, a value rule no other
    field has
  - Capture `locals()` once immediately before the pass and build `supplied` from
    the registry keys, rather than 25 explicit `"name": name` pairs where a typo
    yields `None` and fails silently. Add
    `test_every_registry_key_is_a_build_monitor_data_parameter`, comparing the
    registry keys against `inspect.signature(_build_monitor_data).parameters`
  - Emit each supported field, collect the withheld, then call
    `_warn_withheld_v2_fields(withheld, stacklevel=4)`
  - The pass stays at the **tail**, where the `>= 2.0` block is. Nothing enters
    the preamble: a preamble-sited pass needs a second registry walk and would
    put a warning ahead of the three `ValueError`s, describing a call that never
    happens
  - **Do not touch**: the `1.22` gate on `parent`; the `1.23` gates on
    `invertKeyword`, `timeout` and `gamedigGivenPortOnly`; the `1.23.1` gate in
    `set_settings`; the `1.22` / `1.23` / `2.0` gates in
    `_build_status_page_data`; every unconditional type-specific emission; and
    the preamble's `TypeError` and three `ValueError`s, which fire on both majors
  - Preserve the preamble order exactly: `conditions` `TypeError`, then
    `_check_conditions_supported`, then `_check_monitor_type_supported`
  - _Requirements: 1.1, 1.2, 1.10, 1.11, 2.7, 4.2, 4.5, 4.7, 5.1, 5.2, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 9.5_

- [x] 10. Wire the edit path in `edit_monitor`
  - Compute the withheld set from `kwargs` **before** the merge, warn with
    `stacklevel=3`, then merge only the keys that were not withheld:
    `data.update({k: v for k, v in kwargs.items() if k not in withheld})`
  - Deleting keys after the merge is the wrong shape: `del data[key]` cannot
    distinguish a key the caller supplied from one `get_monitor` returned, so a
    monitor carrying a v2-only column would lose it on any unrelated edit
  - Warn **before** `self.get_monitor(id_)`, so an escalated warning costs no
    `getMonitor` round trip — the property the `conditions` guard already holds
  - Pass no monitor type, so type-restricted entries are skipped on this path.
    Enforcing the type dimension here would newly drop fields on 2.x, and reading
    the type from `kwargs` would yield `None` for an ordinary
    `edit_monitor(id_, saveResponse=True)` and omit the field at every version
  - Leave both existing guards reading `kwargs.get(...)` ahead of everything
  - _Requirements: 1.6, 2.5, 2.7, 9.2, 9.3, 9.6_

- [x] 11. Confirm green and re-verify the boundary
  - `pytest -v` fully green, including the two untouched gate classes in the same
    run
  - Re-run the phase 3 red cases to confirm they now pass for the right reason,
    not because an assertion was loosened
  - _Requirements: 8.9, 8.11_

---

## Phase 5 — documentation and record-keeping, in the same merged change

- [ ] 12. Write the single normative rule statement
  - New labelled section in `docs/api.rst` after `Main Interface`:
    `.. _v2-only-fields:` / `Version-gated monitor fields`
  - State all five required things: the class the rule governs, where a caller
    finds each field's floor, how a caller learns a field was withheld, the
    `UnsupportedFieldWarning` name to filter on, and `conditions` as the single
    named exception with the test quoted verbatim — *a field that changes the
    monitor's verdict raises; a field that changes how the check runs is withheld
    with a Signal*
  - Phrase it as a rule about **fields the connected server does not implement**,
    not about the 26 names or about "2.0", so extending it later is registry rows
    plus a sentence rather than a new policy
  - Add a one-line cross-reference to `add_monitor` and `edit_monitor` — in the
    hand-written docstring, not the generated `monitor_docstring` block — that
    restates nothing. Phrase them as sentences that survive being unrendered in a
    REPL
  - `docs/make.bat html` runs warning-free and the `:ref:` resolves
  - _Requirements: 1.3, 1.4, 1.7, 3.1, 3.2, 3.6, 3.7, 3.8_

- [ ] 13. Update the cross-spec record and the changelog
  - `CHANGELOG.md` under the shipping heading: the rule, every field whose
    behaviour changes, what a caller relying on the old behaviour now observes,
    that the change is **non-breaking**, and that `conditions` is unchanged from
    2.3.1. State the one behavioural delta honestly — on the edit path a
    caller-supplied below-floor field that 2.3.1 merged through to the server is
    now withheld, turning a probable `SQLITE_ERROR` into a warning
  - Bump `uptime_kuma_api/__version__.py` to **2.4.0** — `feat`, minor. Nothing
    here was broken; what ships is predictability across the class
  - Extend requirement 13.3's existing NARROWED annotation in
    `.kiro/specs/uptime-kuma-v2-support-backlog/requirements.md`: quote
    `without raising an error or logging a warning`, and record that 13.3 rested
    on the premise that a dropped field fails observably, which the #12
    verification falsified for a whole subclass of fields
  - Record in `## Cross-Spec Policy Conflict` of
    `.kiro/specs/conditions-field-v1-regression/design.md` that the `conditions`
    raise is **retained** as the single named exception, justified by the
    requirement 1.4 test
  - Fix the stale pointers in `v2-only-monitor-types-gate/design.md` ("Why the
    gate is 2.0 and not per-type") and the 2.3.1 CHANGELOG note, both of which
    send the reader to #14 for the `SYSTEM_SERVICE` floor that **#28** now owns
  - _Requirements: 3.3, 3.4, 3.5, 9.4_

- [ ] 14. Open the two tracked follow-ups
  - The un-inventoried v2-only surfaces, per decision 5. Carry forward what the
    requirements now record: `_build_status_page_data` already has a `2.0` gate
    with a **third** pattern — `analyticsType` / `analyticsId` /
    `analyticsScriptUrl` sent unconditionally including when `None`, because the
    v2 server rejects the whole save with `Invalid analytics type` when the key
    is absent — so withholding is not an available outcome there; and maintenance
    and settings carry no `2.0` gate at all, which does not prove they have no
    v2-only surface, since an ungated one is the #12 defect class
  - Link **#28** as consuming the name-to-floor shape this change establishes
  - _Requirements: 1.6, 4.8_
