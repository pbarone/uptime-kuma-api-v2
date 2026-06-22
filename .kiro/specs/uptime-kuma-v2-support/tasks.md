# Implementation Plan: Uptime Kuma v2 Support

## Overview

This plan implements Uptime Kuma v2 compatibility for the `uptime-kuma-api` Python library. The approach is:
1. Cherry-pick existing upstream PRs (#87 and #88) to preserve attribution
2. Apply additional code fixes on top (move conditions to common, safe pop, type validation)
3. Update documentation and docstrings
4. Add tests (unit + property-based)
5. Update packaging/versioning

All tasks assume we are on the `v2-support` branch and cherry-picking from local `pr-87` and `pr-88` branches.

## Tasks

- [ ] 1. Cherry-pick upstream PRs
  - [ ] 1.1 Cherry-pick PR #87 (status page autoRefreshInterval fix)
    - Run `git cherry-pick pr-87` to bring in the one-line `status_page.pop("autoRefreshInterval")` fix in `save_status_page`
    - _Requirements: 4.1, 5.1, 5.4_

  - [ ] 1.2 Cherry-pick PR #88 (DNS conditions support)
    - Run `git cherry-pick pr-88` to bring in the `conditions` parameter added to `_build_monitor_data` (DNS section only)
    - _Requirements: 3.1, 5.2, 5.4_

- [ ] 2. Apply code fixes to `uptime_kuma_api/api.py`
  - [ ] 2.1 Fix PR #87 to use safe pop with default
    - Change `status_page.pop("autoRefreshInterval")` to `status_page.pop("autoRefreshInterval", None)` in `save_status_page`
    - This prevents KeyError when connected to v1 instances where the field doesn't exist
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ] 2.2 Move `conditions` parameter from DNS section to common parameters
    - In `_build_monitor_data`, move the `conditions: list = None` parameter to the common parameter section (after `httpBodyEncoding`)
    - Move the `data.update({"conditions": ...})` call from the DNS-specific section into the common data dict construction at the top of the method body
    - Replace with: `data["conditions"] = conditions if conditions is not None else []`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.2, 5.3_

  - [ ] 2.3 Add type validation for `conditions` parameter
    - Before the `data["conditions"] = ...` line, add: `if conditions is not None and not isinstance(conditions, list): raise TypeError("conditions must be a list or None")`
    - _Requirements: 1.5_

- [ ] 3. Checkpoint - Verify core fixes
  - Ensure all existing tests pass with the code changes. Ask the user if questions arise.

- [ ] 4. Update documentation and docstrings
  - [ ] 4.1 Update `uptime_kuma_api/docstrings.py`
    - Add `:param list, optional conditions: Conditions for monitor validation (e.g., expected DNS records, response assertions). Each condition is a dict with fields: ``type``, ``variable``, ``operator``, ``value``, ``andOr``. Defaults to an empty list ``[]``.` to `monitor_docstring()` in the common parameters section (after `httpBodyEncoding`)
    - _Requirements: 1.2, 1.3, 3.3_

  - [ ] 4.2 Update `CHANGELOG.md`
    - Add a new `### Release 2.0.0` section at the top with Features (v2 support, conditions parameter, upstream PRs) and Bugfixes (NOT NULL constraint fix, autoRefreshInterval TypeError fix)
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 4.3 Update `uptime_kuma_api/__version__.py`
    - Change `__version__ = "1.2.1"` to `__version__ = "2.0.0"`
    - _Requirements: 5.3_

  - [ ] 4.4 Update `README.md` supported versions table
    - Add row: `| 2.0.0 - 2.4.0 | 2.0.0+ |` at the top of the versions table
    - Keep existing v1 rows intact
    - _Requirements: 2.1, 6.1_

- [ ] 5. Checkpoint - Verify docs and packaging
  - Ensure all tests still pass after doc changes. Ask the user if questions arise.

- [ ] 6. Add unit tests
  - [ ] 6.1 Add `test_monitor_conditions` to `tests/test_monitor.py`
    - Create a test that adds an HTTP monitor with explicit `conditions` list containing one condition dict, verifies round-trip via `do_test_monitor_type`
    - Skip test if version < 2.0 with `self.skipTest("Unsupported in this Uptime Kuma version")`
    - _Requirements: 1.2, 3.3, 6.1_

  - [ ] 6.2 Add `test_monitor_dns_conditions` to `tests/test_monitor.py`
    - Create a test that adds a DNS monitor with DNS-specific conditions (variable="record", operator="contains"), verifies round-trip via `do_test_monitor_type`
    - Skip test if version < 2.0
    - _Requirements: 3.1, 3.4, 5.2, 6.4_

- [ ]* 7. Add property-based tests
  - [ ]* 7.1 Write property test for default conditions is empty list
    - **Property 1: Default conditions is empty list**
    - Use Hypothesis to generate random MonitorType values and verify `_build_monitor_data` output contains `"conditions": []` when conditions param is omitted
    - **Validates: Requirements 1.1, 2.2, 3.2**

  - [ ]* 7.2 Write property test for conditions pass-through
    - **Property 2: Conditions pass-through preserves input exactly**
    - Use Hypothesis to generate random lists of random dicts, pass as `conditions`, verify output `"conditions"` == input list
    - **Validates: Requirements 1.2, 3.1, 3.3, 3.4**

  - [ ]* 7.3 Write property test for conditions accepted for all monitor types
    - **Property 3: Conditions accepted for all monitor types**
    - Use Hypothesis to iterate all MonitorType enum values with random conditions lists, verify no exception and `"conditions"` in output
    - **Validates: Requirements 1.3, 5.3**

  - [ ]* 7.4 Write property test for None conditions converts to empty list
    - **Property 4: None conditions converts to empty list**
    - Use Hypothesis to generate random MonitorType values with `conditions=None`, verify output `"conditions"` == `[]`
    - **Validates: Requirements 1.4, 7.4**

  - [ ]* 7.5 Write property test for invalid conditions type raises TypeError
    - **Property 5: Invalid conditions type raises TypeError**
    - Use Hypothesis to generate non-list non-None values (int, str, dict, bool, tuple), verify `TypeError` raised
    - **Validates: Requirements 1.5**

  - [ ]* 7.6 Write property test for malformed condition dicts pass through
    - **Property 6: Malformed condition dicts pass through without client-side rejection**
    - Use Hypothesis to generate dicts with random subsets of condition fields, verify no exception and dicts preserved unchanged in output
    - **Validates: Requirements 3.5**

  - [ ]* 7.7 Write property test for status page autoRefreshInterval tolerance
    - **Property 7: Status page save tolerates presence or absence of autoRefreshInterval**
    - Use Hypothesis to generate status page dicts with/without `autoRefreshInterval`, verify pop-and-build doesn't raise
    - **Validates: Requirements 4.1, 4.2, 4.3**

- [ ] 8. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Cherry-pick tasks (1.1, 1.2) must run first to establish the git history with proper attribution
- Code fixes (2.1-2.3) build on cherry-picked code and must run after task 1
- The `edit_monitor` method doesn't go through `_build_monitor_data` — it merges the fetched dict with user kwargs and sends directly. The `conditions` field is preserved from fetched data naturally (Requirement 7.1)
- Integration tests against live v2.4.0 instances are run manually outside this task list (Requirement 6)
- Property tests use the [Hypothesis](https://hypothesis.readthedocs.io/) library for Python

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1", "2.2"] },
    { "id": 3, "tasks": ["2.3"] },
    { "id": 4, "tasks": ["4.1", "4.2", "4.3", "4.4"] },
    { "id": 5, "tasks": ["6.1", "6.2"] },
    { "id": 6, "tasks": ["7.1", "7.2", "7.3", "7.4", "7.5", "7.6", "7.7"] }
  ]
}
```
