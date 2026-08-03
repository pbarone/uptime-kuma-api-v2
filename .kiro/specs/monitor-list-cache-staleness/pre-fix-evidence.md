# Pre-fix evidence — requirement 2.9

Requirement 2.9 demands regression tests *demonstrated to fail against the
unfixed code before the fix lands*. This file is that artifact for tasks 1 → 2:
the verbatim pre-fix failure of tests 14 and 15 from
`tests/test_monitor_cache_v2.py`.

Copy the "Verbatim pytest output" section below into the PR description when the
fix is raised.

## Provenance

| | |
|---|---|
| Recorded by | task 2 of the `monitor-list-cache-staleness` bugfix spec |
| Code state | **unfixed** — no delta handlers, no `_refresh_monitor_list`, guards read the cache directly |
| Command | `pytest tests/test_monitor_cache_v2.py -v` (invoked as `.venv\Scripts\python.exe -m pytest tests/test_monitor_cache_v2.py -v`) |
| Environment | Windows, Python 3.13.3, pytest 9.1.1, pluggy 1.6.0 |
| Result | **2 failed in 0.88s** — the expected outcome |

## Verdict

Both tests failed, both for the right reason.

| Test | Exception type | Exception message | Raised at | `_call` state |
|---|---|---|---|---|
| 14 — `test_delete_monitor_sends_delete_for_id_present_only_after_refresh` | `uptime_kuma_api.exceptions.UptimeKumaException` | `monitor does not exist` | `uptime_kuma_api\api.py:1585`, inside the real `delete_monitor` guard | **never invoked** — `_call events sent: []` |
| 15 — `test_delete_monitor_tag_sends_delete_for_tag_present_only_after_refresh` | `uptime_kuma_api.exceptions.UptimeKumaException` | `monitor tag does not exist` | `uptime_kuma_api\api.py:1809`, inside the real `delete_monitor_tag` guard | **never invoked** — `_call events sent: []` |

**Failure reason verified, not just the failure.** Task 2 requires the traceback
to come from the guard raising rather than from an `AttributeError` on a
post-fix name the harness leaked. Confirmed on both counts:

- Each traceback's innermost frame is production code — `api.py:1585` and
  `api.py:1809` — with the guard's own `raise UptimeKumaException(...)` line
  shown, and pytest prints the real `delete_monitor` / `delete_monitor_tag`
  bodies, so the tests exercised the real guards rather than a reimplementation.
- No `AttributeError` appears anywhere in the output. The harness resolved
  against pre-fix names only, so task 1 needs no correction.
- `_call events sent: []` in both failure messages is the second half of the
  diagnosis: the guard rejected *before* any request reached the transport, so
  the delete never went to the server. This is exactly defect behaviours 1.2 and
  1.6 from `bugfix.md`.

The stale/fresh split each test sets up is the counterexample itself: the server
answers `getMonitorList` with the entity present, and the guard still rejects,
because it decides from the session-stale cache and never refreshes.

- Test 14 counterexample — stale cache ids `{1, 2}`, fresh server ids
  `{1, 2, 7}`, target `7` (an **int**, which is what distinguishes this from the
  already-shipped #91 string-id coercion defect).
- Test 15 counterexample — stale cache tags for monitor 1 `{(9, 1, "other")}`,
  fresh server tags `{(9, 1, "other"), (3, 1, "prod")}`, target
  `(tag_id=3, monitor_id=1, value="prod")`.

## Verbatim pytest output

```
============================================ test session starts =============================================
platform win32 -- Python 3.13.3, pytest-9.1.1, pluggy-1.6.0 -- F:\Dev\uptime-kuma-api-v2\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: F:\Dev\uptime-kuma-api-v2
collecting ... collected 2 items

tests/test_monitor_cache_v2.py::TestGuardsDecideOnFreshData::test_delete_monitor_sends_delete_for_id_present_only_after_refresh FAILED [ 50%]
tests/test_monitor_cache_v2.py::TestGuardsDecideOnFreshData::test_delete_monitor_tag_sends_delete_for_tag_present_only_after_refresh FAILED [100%]

================================================== FAILURES ==================================================
_______ TestGuardsDecideOnFreshData.test_delete_monitor_sends_delete_for_id_present_only_after_refresh _______

self = <test_monitor_cache_v2.TestGuardsDecideOnFreshData testMethod=test_delete_monitor_sends_delete_for_id_present_only_after_refresh>

    def test_delete_monitor_sends_delete_for_id_present_only_after_refresh(self):
        """Test 14 -- monitor 7 is absent from the stale cache, present on the
        server. ``delete_monitor(7)`` must send ``deleteMonitor``.

        **Validates: Requirements 1.2, 2.2**
        """
        stale = cache_of(monitor(1), monitor(2))
        fresh = cache_of(monitor(1), monitor(2), monitor(7))
        api, delete_monitor = make_guard_api("delete_monitor", stale, fresh)

        try:
>           result = delete_monitor(7)
                     ^^^^^^^^^^^^^^^^^

tests\test_monitor_cache_v2.py:154:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <MagicMock spec='UptimeKumaApi' id='2236019969728'>, id_ = 7

    def delete_monitor(self, id_: int) -> dict:
        """
        Deletes a monitor.

        :param int id_: The monitor id.
        :return: The server response.
        :rtype: dict
        :raises UptimeKumaException: If the server returns an error.

        Example::

            >>> api.delete_monitor(1)
            {
                'msg': 'Deleted Successfully.'
            }
        """
        with self.wait_for_event(Event.MONITOR_LIST):
            ids = [i["id"] for i in self.get_monitors()]
            try:
                id_ = int(id_)
            except (TypeError, ValueError):
                pass
            if id_ not in ids:
>               raise UptimeKumaException("monitor does not exist")
E               uptime_kuma_api.exceptions.UptimeKumaException: monitor does not exist

uptime_kuma_api\api.py:1585: UptimeKumaException

During handling of the above exception, another exception occurred:

self = <test_monitor_cache_v2.TestGuardsDecideOnFreshData testMethod=test_delete_monitor_sends_delete_for_id_present_only_after_refresh>

    def test_delete_monitor_sends_delete_for_id_present_only_after_refresh(self):
        """Test 14 -- monitor 7 is absent from the stale cache, present on the
        server. ``delete_monitor(7)`` must send ``deleteMonitor``.

        **Validates: Requirements 1.2, 2.2**
        """
        stale = cache_of(monitor(1), monitor(2))
        fresh = cache_of(monitor(1), monitor(2), monitor(7))
        api, delete_monitor = make_guard_api("delete_monitor", stale, fresh)

        try:
            result = delete_monitor(7)
        except UptimeKumaException as e:
>           self.fail(
                "delete_monitor(7) raised {0}(\"{1}\") although the server has "
                "monitor 7; _call events sent: {2}".format(
                    type(e).__name__, e, sent_events(api)
                )
            )
E           AssertionError: delete_monitor(7) raised UptimeKumaException("monitor does not exist") although the server has monitor 7; _call events sent: []

tests\test_monitor_cache_v2.py:156: AssertionError
____ TestGuardsDecideOnFreshData.test_delete_monitor_tag_sends_delete_for_tag_present_only_after_refresh _____

self = <test_monitor_cache_v2.TestGuardsDecideOnFreshData testMethod=test_delete_monitor_tag_sends_delete_for_tag_present_only_after_refresh>

    def test_delete_monitor_tag_sends_delete_for_tag_present_only_after_refresh(self):
        """Test 15 -- the stale cache entry for monitor 1 carries no matching
        ``(tag_id, monitor_id, value)`` triple, the server's does.
        ``delete_monitor_tag`` must send ``deleteMonitorTag``.

        **Validates: Requirements 1.6, 2.6**
        """
        stale = cache_of(monitor(1, tags=[tag(9, 1, "other")]))
        fresh = cache_of(monitor(1, tags=[tag(9, 1, "other"), tag(3, 1, "prod")]))
        api, delete_monitor_tag = make_guard_api("delete_monitor_tag", stale, fresh)

        try:
>           result = delete_monitor_tag(tag_id=3, monitor_id=1, value="prod")
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests\test_monitor_cache_v2.py:178:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <MagicMock spec='UptimeKumaApi' id='2236019970736'>, tag_id = 3, monitor_id = 1, value = 'prod'

    def delete_monitor_tag(self, tag_id: int, monitor_id: int, value: str = "") -> dict:
        """
        Delete a tag from a monitor.

        :param int tag_id: Id of the tag to remove.
        :param int monitor_id: Id of monitor to remove the tag from.
        :param str, optional value: Value of the tag., defaults to ""
        :return: The server response.
        :rtype: dict
        :raises UptimeKumaException: If the server returns an error.

        Example::

            >>> api.delete_monitor_tag(
            ...     tag_id=1,
            ...     monitor_id=1,
            ...     value="test"
            ... )
            {
                'msg': 'Deleted Successfully.'
            }
        """
        with self.wait_for_event(Event.MONITOR_LIST):
            tags = [
                {
                    "monitor_id": y["monitor_id"],
                    "tag_id": y["tag_id"],
                    "value": y["value"]
                } for x in [
                    i.get("tags") for i in self.get_monitors()
                ] for y in x
            ]
            if {"monitor_id": monitor_id, "tag_id": tag_id, "value": value} not in tags:
>               raise UptimeKumaException("monitor tag does not exist")
E               uptime_kuma_api.exceptions.UptimeKumaException: monitor tag does not exist

uptime_kuma_api\api.py:1809: UptimeKumaException

During handling of the above exception, another exception occurred:

self = <test_monitor_cache_v2.TestGuardsDecideOnFreshData testMethod=test_delete_monitor_tag_sends_delete_for_tag_present_only_after_refresh>

    def test_delete_monitor_tag_sends_delete_for_tag_present_only_after_refresh(self):
        """Test 15 -- the stale cache entry for monitor 1 carries no matching
        ``(tag_id, monitor_id, value)`` triple, the server's does.
        ``delete_monitor_tag`` must send ``deleteMonitorTag``.

        **Validates: Requirements 1.6, 2.6**
        """
        stale = cache_of(monitor(1, tags=[tag(9, 1, "other")]))
        fresh = cache_of(monitor(1, tags=[tag(9, 1, "other"), tag(3, 1, "prod")]))
        api, delete_monitor_tag = make_guard_api("delete_monitor_tag", stale, fresh)

        try:
            result = delete_monitor_tag(tag_id=3, monitor_id=1, value="prod")
        except UptimeKumaException as e:
>           self.fail(
                "delete_monitor_tag(tag_id=3, monitor_id=1, value=\"prod\") raised "
                "{0}(\"{1}\") although the server has that tag; _call events "
                "sent: {2}".format(type(e).__name__, e, sent_events(api))
            )
E           AssertionError: delete_monitor_tag(tag_id=3, monitor_id=1, value="prod") raised UptimeKumaException("monitor tag does not exist") although the server has that tag; _call events sent: []

tests\test_monitor_cache_v2.py:180: AssertionError
========================================== short test summary info ===========================================
FAILED tests/test_monitor_cache_v2.py::TestGuardsDecideOnFreshData::test_delete_monitor_sends_delete_for_id_present_only_after_refresh - AssertionError: delete_monitor(7) raised UptimeKumaException("monitor does not exist") although the server...
FAILED tests/test_monitor_cache_v2.py::TestGuardsDecideOnFreshData::test_delete_monitor_tag_sends_delete_for_tag_present_only_after_refresh - AssertionError: delete_monitor_tag(tag_id=3, monitor_id=1, value="prod") raised UptimeKumaException("monit...
============================================= 2 failed in 0.88s ==============================================
```

## After the fix

Task 4.5 re-runs these same two tests unmodified and expects both to pass. Do
not edit tests 14 or 15 to get there — the paired red-then-green on identical
test code is what the evidence rests on.

### Green run — recorded by task 4.5

| | |
|---|---|
| Recorded by | task 4.5 of the `monitor-list-cache-staleness` bugfix spec |
| Code state | **fixed** — change groups 4.1-4.4 applied: two `Event` members, both delta handlers, `_refresh_monitor_list` called first inside each guard's `wait_for_event`, `wait_for_event` comment block |
| Command | `pytest tests/test_monitor_cache_v2.py -v` (invoked as `.venv\Scripts\python.exe -m pytest tests/test_monitor_cache_v2.py -v`) |
| Environment | Windows, Python 3.13.3, pytest 9.1.1, pluggy 1.6.0 — identical to the red run |
| Result | **14 passed, 6 subtests passed in 0.45s** |

Tests 14 and 15, the two that failed above, both pass:

```
tests/test_monitor_cache_v2.py::TestGuardsDecideOnFreshData::test_delete_monitor_sends_delete_for_id_present_only_after_refresh PASSED [  7%]
tests/test_monitor_cache_v2.py::TestGuardsDecideOnFreshData::test_delete_monitor_tag_sends_delete_for_tag_present_only_after_refresh PASSED [ 14%]
```

Passing means each guard now reaches the transport for an entity present only in
the server's fresh view: test 14's `api._call.assert_any_call("deleteMonitor", 7)`
and test 15's `api._call.assert_any_call("deleteMonitorTag", (3, 1, "prod"))` both
hold, where the red run recorded `_call events sent: []` for both. The counter-
examples are unchanged — stale ids `{1, 2}` vs fresh `{1, 2, 7}`, target int `7`;
stale tags `{(9, 1, "other")}` vs fresh `{(9, 1, "other"), (3, 1, "prod")}`.

The remaining 12 tests and 6 subtests in the file are the task-3 preservation
baseline; task 4.6 is what signs those off.

### Test code unchanged between the two runs

The red-then-green pair only means something if the test code did not move, so
that was checked rather than assumed:

- **The production diff is production-only.** `git diff --stat` after the fix
  shows `uptime_kuma_api/api.py` and `uptime_kuma_api/event.py` and nothing else.
  `tests/test_monitor_cache_v2.py` is still untracked — it has never been
  committed, so there is no committed baseline to diff it against, which is why
  the check below is against this file's recorded output instead of against git.
- **Every line pytest printed pre-fix is byte-identical to the live source.**
  Both test bodies as printed in the red traceback above — 19 lines each,
  docstring through the `self.fail(...)` call — were compared line by line
  against `inspect.getsource` of the live methods. Both matched exactly.
- **The three lines pytest never printed** are the post-`except` assertions
  (`api._call.assert_any_call(...)` and `self.assertEqual(result,
  SERVER_RESPONSE)`), which the red run could not reach because execution
  stopped at `self.fail`. They are outside the recorded output by construction;
  they match what task 1 specified for tests 14 and 15.
- **The shared guard harness needed no edit for the fix.** `make_guard_api`
  discovers which `self` methods to bind for real from the guard's own bytecode
  (`_self_methods_called_by`), so `_refresh_monitor_list` is picked up
  automatically now that the guards call it. That is the design from task 1, and
  it is why no harness change was required to turn these tests green.
