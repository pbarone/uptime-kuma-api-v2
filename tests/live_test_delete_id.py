"""
Live verification for Bug A (#91) -- string monitor ids -- and Bug E (#44) --
socket.io timeouts surfacing as the library's own ``Timeout``.

Not a pytest test. The filename deliberately starts with ``live_test_`` rather
than ``test_``: pytest's default discovery collects ``test_*.py`` and
``*_test.py``, so this prefix keeps the script out of every pytest run,
including a bare ``pytest tests/``. Do not rename it.

SAFETY -- READ FIRST:
    This script CREATES one monitor and DELETES it again. Point it only at a
    disposable instance. ``UPTIME_KUMA_URL`` is expected to be the throwaway
    instance, the same one the other live_test_* scripts target. Nothing else on
    the server is modified: no notifications, proxies, tags, status pages or
    settings are touched.

    The monitor created is of type PUSH, so the server never makes an outbound
    request on its behalf. It is named with the "[TEST] " prefix so
    live_test_cleanup.py would also sweep it up if this script died before its
    own cleanup ran.

Why this script exists at all:
    live_test_cleanup.py already deletes monitors, but it calls
    ``delete_monitor(monitor["id"])`` with the **int** the server returned. That
    is the code path that always worked. Bug A was specifically about **string**
    ids: ``delete_monitor("7")`` compared the string against a list of ints,
    found no match, and raised ``UptimeKumaException: monitor does not exist``
    without ever sending a delete. So no existing live script exercises the
    broken path, and this one does.

    Bug E is about ``_call`` translating ``socketio.exceptions.TimeoutError``
    into the library's ``Timeout`` (a subclass of ``UptimeKumaException``), so
    callers can catch one exception hierarchy instead of leaking a
    socket.io-specific type. The probe emits an event the server has no handler
    for, so no ack ever arrives and the timeout is deterministic. Lowering
    ``api.timeout`` and racing a normal call cannot work on Windows -- see
    Step 4's comment and UPSTREAM_TRIAGE section 8.

TEMPORARY SCAFFOLDING -- remove when the monitor-list cache defect is fixed:
    On Uptime Kuma 2.x the cached monitor list is not refreshed after
    ``add_monitor``, so ``delete_monitor`` rejects an id that demonstrably
    exists (UPSTREAM_TRIAGE section 7). Two things in this script exist only
    because of that defect and must both be deleted once it is fixed:

    1. the explicit ``api._call("getMonitorList")`` cache refresh in Step 2 and
       in cleanup -- a workaround, NOT something the library should ever require
       of callers;
    2. the "KNOWN ISSUE" staleness check in Step 2, which detects the defect
       directly and is informational only: it never affects the exit code, so
       this script keeps reporting on Bug A rather than failing on an unrelated
       known problem.

Output is ASCII only. The Windows console defaults to cp1252 and raises
UnicodeEncodeError on check marks, box-drawing characters and arrows, which has
crashed a script mid-run before. Use PASS / FAIL / SKIP / ->.

Configuration:
    Create/extend tests/.env with:
        UPTIME_KUMA_URL=http://your-disposable-host:3001/
        UPTIME_KUMA_USERNAME=admin
        UPTIME_KUMA_PASSWORD=your-password

Usage:
    .venv/Scripts/python tests/live_test_delete_id.py

Exit code is 0 only if every check passed. A SKIP does not fail the run.
"""
import os
import sys
import time

sys.path.insert(0, ".")

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from uptime_kuma_api import (
    MonitorType,
    Timeout,
    UptimeKumaApi,
    UptimeKumaException,
)

PREFIX = "[TEST] "

results = []
known_issues = []


def record(label: str, ok: bool, detail: str = "") -> bool:
    """Record one check result and report it as it happens."""
    results.append((label, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if detail:
        print(f"          {detail}")
    return ok


def skip(label: str, reason: str) -> None:
    """Record an inconclusive check.

    A timing-dependent probe that quietly reports PASS when it never actually
    exercised the code under test is worse than an honest SKIP, so this is kept
    distinct from both PASS and FAIL and does not affect the exit code.
    """
    results.append((label, None, reason))
    print(f"  SKIP  {label}")
    print(f"          {reason}")


def known_issue(label: str, detail: str) -> None:
    """Report an already-diagnosed defect that this script is not testing.

    Deliberately kept out of ``results``: these lines are informational and must
    never influence the exit code. They exist so the script surfaces a known
    problem instead of silently working around it.
    """
    known_issues.append((label, detail))
    print(f"  INFO  KNOWN ISSUE: {label}")
    print(f"          {detail}")


def main() -> int:
    try:
        url = os.environ["UPTIME_KUMA_URL"]
        username = os.environ["UPTIME_KUMA_USERNAME"]
        password = os.environ["UPTIME_KUMA_PASSWORD"]
    except KeyError as e:
        raise SystemExit(
            f"ABORT: {e.args[0]} is not set. Create tests/.env with "
            "UPTIME_KUMA_URL, UPTIME_KUMA_USERNAME and UPTIME_KUMA_PASSWORD."
        )

    print(f"Target: {url}")
    print("This script creates and deletes ONE monitor. Disposable instances only.")
    print()

    print(f"Connecting to {url} ...")
    api = UptimeKumaApi(url)

    monitor_id = None
    string_delete_ok = False

    try:
        print()
        print("Step 1: login")
        api.login(username, password)
        record("login", True, f"server version {api.version}")

        print()
        print("Step 2: Bug A -- delete_monitor accepts a string id")
        # PUSH means the server never dials out on this monitor's behalf.
        r = api.add_monitor(
            type=MonitorType.PUSH,
            name=f"{PREFIX}Bug A string id",
        )
        monitor_id = r["monitorID"]
        record("created throwaway monitor", True, f"monitorID={monitor_id!r}")

        # --- KNOWN ISSUE probe (informational, does not affect the exit code) ---
        # Detect the monitor-list cache staleness directly, before any refresh.
        # On 2.x the server no longer broadcasts a full monitorList after a
        # mutation (it emits updateMonitorIntoList, which the library has no
        # handler for), so the id just returned by add_monitor is missing from
        # get_monitors(). Remove this block together with the refresh below once
        # the defect is fixed.
        ids_before_refresh = [m["id"] for m in api.get_monitors()]
        if monitor_id not in ids_before_refresh:
            known_issue(
                "monitor-list cache is stale after add_monitor",
                f"id {monitor_id} is absent from get_monitors() immediately after "
                f"add_monitor returned it (cached ids: {ids_before_refresh}). This is "
                "the already-diagnosed 2.x cache defect in UPSTREAM_TRIAGE section 7, "
                "NOT a new problem and NOT a Bug A regression: it reproduces with an "
                "int id too. It gets its own spec. Reported as information only.",
            )
        else:
            print(
                f"  INFO  monitor-list cache already contains id {monitor_id}; the "
                "section-7 staleness did not reproduce here"
            )

        # WORKAROUND for the known cache defect (UPSTREAM_TRIAGE section 7).
        # delete_monitor's existence guard reads the cached monitor list, so
        # without this refresh it rejects the id above and the string-id path
        # under test is never reached -- the step would FAIL for a reason that
        # has nothing to do with Bug A. Callers should NOT have to do this;
        # delete this line when the cache defect is fixed.
        api._call("getMonitorList")

        try:
            # Pre-fix: str(id) never matched the int ids from get_monitors(), so
            # this raised "monitor does not exist" and sent nothing.
            api.delete_monitor(str(monitor_id))
        except Exception as e:
            record(
                f"delete_monitor(str({monitor_id})) does not raise",
                False,
                f"{type(e).__name__}: {e}",
            )
        else:
            string_delete_ok = True
            record(f"delete_monitor(str({monitor_id})) does not raise", True)

            # Same WORKAROUND again (UPSTREAM_TRIAGE section 7): 2.x answers a
            # delete with deleteMonitorFromList, which the library also has no
            # handler for, so without a refresh this read sees the pre-delete
            # cache and reports a successful delete as a failure. Remove when
            # the cache defect is fixed.
            api._call("getMonitorList")
            remaining = [m["id"] for m in api.get_monitors()]
            gone = monitor_id not in remaining
            record(
                "monitor is absent from get_monitors() afterwards",
                gone,
                "" if gone else f"id {monitor_id} is still present -- the delete was not sent",
            )

        print()
        print("Step 3: Bug A -- the not-found guard is preserved")
        try:
            api.delete_monitor("99999999")
        except UptimeKumaException as e:
            ok = "does not exist" in str(e)
            record(
                "numeric string for a missing id still raises 'does not exist'",
                ok,
                "" if ok else f"UptimeKumaException with unexpected message: {e}",
            )
        except Exception as e:
            record(
                "numeric string for a missing id still raises 'does not exist'",
                False,
                f"expected UptimeKumaException, got {type(e).__name__}: {e}",
            )
        else:
            record(
                "numeric string for a missing id still raises 'does not exist'",
                False,
                "no exception raised -- a non-existent id was accepted",
            )

        try:
            # A non-numeric string must not leak the ValueError from the int()
            # coercion; it has to come back as the library's own exception.
            api.delete_monitor("not-an-id")
        except UptimeKumaException as e:
            ok = "does not exist" in str(e)
            record(
                "non-numeric string raises UptimeKumaException, not ValueError",
                ok,
                "" if ok else f"UptimeKumaException with unexpected message: {e}",
            )
        except Exception as e:
            record(
                "non-numeric string raises UptimeKumaException, not ValueError",
                False,
                f"expected UptimeKumaException, got {type(e).__name__}: {e}",
            )
        else:
            record(
                "non-numeric string raises UptimeKumaException, not ValueError",
                False,
                "no exception raised -- a non-numeric id was accepted",
            )

        print()
        print("Step 4: Bug E -- socket.io timeout surfaces as the library Timeout")
        # Shrinking api.timeout and racing a real call cannot produce a timeout
        # on Windows. socketio.Client.call raises only when its ack
        # threading.Event.wait() expires, and measured Event.wait() granularity
        # on this platform floors around 15 ms while a getTags round-trip is
        # 2.3-6.0 ms -- the ack always wins, at any timeout value, including
        # 0.1 ms. See UPSTREAM_TRIAGE section 8.
        #
        # So emit an event the server has no handler for instead: no ack ever
        # arrives, the wait runs its full course, and the timeout is
        # deterministic. _call is private, but no public method maps to an
        # unhandled event, and reaching _call's translation is the whole point
        # of the probe. The event name is deliberately ours so it is obvious
        # where it came from if anyone reads the server log.
        #
        # The timeout is also lowered on the already-connected instance rather
        # than constructing UptimeKumaApi(url, timeout=...): connect() passes
        # wait_timeout=self.timeout, so a tiny timeout would fail during
        # __init__ and never reach _call at all.
        unhandled_event = "uptimeKumaApiNoSuchEvent"
        original_timeout = api.timeout
        try:
            api.timeout = 2
            started = time.monotonic()
            try:
                api._call(unhandled_event)
            except Timeout as e:
                elapsed_ms = (time.monotonic() - started) * 1000
                ok = isinstance(e, UptimeKumaException)
                record(
                    "timed-out _call raises Timeout (a UptimeKumaException)",
                    ok,
                    f"waited {elapsed_ms:.1f} ms for an ack to '{unhandled_event}', "
                    f"then got {e!r}"
                    if ok
                    else f"Timeout is not a UptimeKumaException: {type(e).__mro__}",
                )
            except Exception as e:
                record(
                    "timed-out _call raises Timeout (a UptimeKumaException)",
                    False,
                    f"expected uptime_kuma_api.Timeout, got {type(e).__name__}: {e}",
                )
            else:
                skip(
                    "timed-out _call raises Timeout (a UptimeKumaException)",
                    f"INCONCLUSIVE: the server acknowledged '{unhandled_event}', an event "
                    "it has no handler for, so the call returned instead of timing out and "
                    "the translation path was never entered. Nothing about the library "
                    "misbehaved, so this is not a FAIL; nothing was exercised, so it is not "
                    "a PASS. If this appears, the server gained a catch-all ack and this "
                    "probe needs a different unacknowledged event. The unit suite covers "
                    "the translation deterministically.",
                )
        finally:
            api.timeout = original_timeout

    finally:
        print()
        print("Cleanup")
        if monitor_id is not None and not string_delete_ok:
            # Step 2's string-id delete failed, so the monitor is still there.
            # Remove it with the int id, which is the path that always worked,
            # rather than leaving an orphan behind.
            print(
                f"  string-id delete did not succeed; falling back to "
                f"delete_monitor({monitor_id}) with the int id"
            )
            try:
                # Same WORKAROUND as Step 2 for the known cache defect
                # (UPSTREAM_TRIAGE section 7): without the refresh the guard
                # rejects the int id as well and the monitor is orphaned.
                # Remove when the cache defect is fixed.
                api._call("getMonitorList")
                api.delete_monitor(monitor_id)
                print(f"  deleted monitor {monitor_id} via the int-id fallback")
            except Exception as e:
                print(f"  FAILED to delete monitor {monitor_id}: {type(e).__name__}: {e}")
                print(f"  Remove '{PREFIX}Bug A string id' manually, or run "
                      "tests/live_test_cleanup.py")
        elif monitor_id is not None:
            print(f"  monitor {monitor_id} already removed by the string-id delete")
        else:
            print("  nothing to delete (no monitor was created)")
        api.disconnect()
        print("  disconnected")

    passed = sum(1 for _, ok, _ in results if ok is True)
    failed = sum(1 for _, ok, _ in results if ok is False)
    skipped = sum(1 for _, ok, _ in results if ok is None)

    print()
    print("=" * 60)
    print(f"  {passed} passed, {failed} failed, {skipped} skipped, "
          f"{len(results)} checks total")
    print("=" * 60)

    if failed:
        print()
        print("Failed checks:")
        for label, ok, detail in results:
            if ok is False:
                print(f"  {label}")
                if detail:
                    print(f"    {detail}")

    if skipped:
        print()
        print("Skipped checks:")
        for label, ok, detail in results:
            if ok is None:
                print(f"  {label}")
                print(f"    {detail}")

    if known_issues:
        print()
        print("Known issues observed (informational, exit code unaffected):")
        for label, detail in known_issues:
            print(f"  {label}")
            print(f"    {detail}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
