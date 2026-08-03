"""
Live verification for the ``conditions`` v1 regression -- ``add_monitor()`` must
work against an Uptime Kuma 1.23.x server.

Not a pytest test. The filename deliberately starts with ``live_test_`` rather
than ``test_``: pytest's default discovery collects ``test_*.py`` and
``*_test.py``, so this prefix keeps the script out of every pytest run,
including a bare ``pytest tests/``. Do not rename it. CI is unaffected by this
file.

SAFETY -- READ FIRST:
    This script CREATES monitors. Point it ONLY at a disposable, throwaway
    Uptime Kuma 1.23.x container that holds nothing you care about. Never point
    it at a real instance.

    It deliberately does NOT read the ``UPTIME_KUMA_URL`` key the other
    live_test_* scripts use, so it cannot accidentally hit the 2.x instance
    those target. It reads its own ``UPTIME_KUMA_V1_*`` keys and refuses to run
    if the URL is unset -- there is no default.

    A second guard follows: the server must report a version starting with
    ``1.23``, or the run aborts before creating anything. That is both a
    correctness guard (the whole run is meaningless against a v2 server) and a
    second line of defence against a mistargeted URL.

What is under test:
    ``_build_monitor_data`` used to emit the Uptime Kuma 2.x-only ``conditions``
    field from the unconditional common ``data`` dict, so EVERY
    ``add_monitor()`` call against a 1.x server sent a column the v1 schema does
    not have and the insert was rejected with::

        SQLITE_ERROR: table monitor has no column named conditions

    No caller opt-in was required -- the default path was enough, which made the
    most-used public method in the library unusable on v1. The regression
    shipped in v2.1.0, v2.2.0 and v2.2.1.

    The acceptance criterion is step 3 below: ``add_monitor()`` succeeding
    through the real public method with **no** ``conditions`` argument and **no**
    ``pop("conditions")`` workaround -- the workaround that was needed to make
    the original discovery run complete.

Why the round-trip matters:
    "The server didn't reject it" is not verification. Each created monitor is
    read back with ``get_monitor()`` and the returned fields are compared
    against what was sent (ABSENT / MISMATCH), so a silently dropped or
    renamed field shows up as a failure rather than as success.

Why the explicit-``conditions`` cases are checked too:
    An explicitly requested ``conditions`` on a pre-2.0 server now raises
    ``UptimeKumaException`` instead of being silently discarded, because
    ``conditions`` defines the monitor's up/down semantics: a silent drop would
    produce a monitor that reports success against criteria the caller never
    set. Those checks also confirm the guard raises *before* any server call, by
    verifying no monitor was created.

Output is ASCII only. The Windows console defaults to cp1252 and raises
UnicodeEncodeError on check marks, box-drawing characters and arrows, which has
crashed a script mid-run before. Use PASS / FAIL / ->.

Configuration:
    Start a disposable container, for example::

        docker run -d --name kuma-v1-conditions -p 3023:3001 louislam/uptime-kuma:1.23.2

    Then set these keys (in the environment or in tests/.env). They are
    referenced by name only; values are never printed by this script:

        UPTIME_KUMA_V1_URL=http://your-disposable-host:3023/
        UPTIME_KUMA_V1_USERNAME=admin
        UPTIME_KUMA_V1_PASSWORD=a-throwaway-password

    A fresh container has no admin user, so the script bootstraps it itself:
    ``need_setup()`` -> ``setup(username, password)`` -> ``login(...)``. On a
    container that is already set up it skips straight to ``login(...)``, so the
    credentials must match the ones it was set up with. Uptime Kuma requires a
    password of at least 6 characters.

    Teardown destroys all state, since the container runs without a volume::

        docker rm -f kuma-v1-conditions

Usage:
    .venv/Scripts/python tests/live_test_conditions_v1.py

Exit code is 0 only if every check passed.
"""
import json
import os
import sys

sys.path.insert(0, ".")

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from uptime_kuma_api import (
    MonitorType,
    UptimeKumaApi,
    UptimeKumaException,
)

REQUIRED_VERSION_PREFIX = "1.23"

# A condition list of the shape v2 accepts. On a v1 server this must never
# reach the wire.
SAMPLE_CONDITIONS = [
    {
        "type": "expression",
        "variable": "response_status",
        "operator": "==",
        "value": "200",
        "andOr": "",
    }
]

results = []


def record(label: str, ok: bool, detail: str = "") -> bool:
    """Record one check result and report it as it happens."""
    results.append((label, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if detail:
        print(f"          {detail}")
    return ok


def equivalent(expected, actual) -> bool:
    """
    Compare a sent value against a returned value, tolerating the type coercion
    Uptime Kuma applies on the way through its database.

    Deliberately tolerant about representation (bool as 0/1, numbers as
    strings, lists as JSON strings) and strict about actual value differences.
    Same helper as live_test_create.py, kept local so this script stands alone.
    """
    if expected == actual:
        return True

    if isinstance(expected, bool):
        if isinstance(actual, (int, float)) and not isinstance(actual, bool):
            return bool(actual) is expected
        if isinstance(actual, str):
            lowered = actual.strip().lower()
            if lowered in ("1", "true"):
                return expected is True
            if lowered in ("0", "false"):
                return expected is False
        return False

    if isinstance(expected, (int, float)) and isinstance(actual, str):
        try:
            return float(actual) == float(expected)
        except ValueError:
            return False
    if isinstance(expected, str) and isinstance(actual, (int, float)) \
            and not isinstance(actual, bool):
        try:
            return float(expected) == float(actual)
        except ValueError:
            return False

    if isinstance(expected, list) and isinstance(actual, str):
        try:
            return json.loads(actual) == expected
        except (ValueError, TypeError):
            return False

    return False


def check_round_trip(label: str, sent: dict, got: dict) -> bool:
    """Verify every field in `sent` came back intact in `got`."""
    absent = [key for key in sent if key not in got]
    mismatched = [
        f"{key}: sent {value!r}, got {got[key]!r}"
        for key, value in sent.items()
        if key in got and not equivalent(value, got[key])
    ]

    parts = []
    if absent:
        parts.append("ABSENT: " + ", ".join(absent))
    if mismatched:
        parts.append("MISMATCH: " + "; ".join(mismatched))

    return record(label, not parts, "  ".join(parts))


def read_config() -> tuple:
    """Read the v1 target from the environment, refusing to guess at anything."""
    url = os.environ.get("UPTIME_KUMA_V1_URL")
    if not url:
        raise SystemExit(
            "ABORT: UPTIME_KUMA_V1_URL is not set, and this script will not\n"
            "       default to any address.\n"
            "\n"
            "       It CREATES monitors, so it must only ever be pointed at a\n"
            "       disposable Uptime Kuma 1.23.x container. Start one with:\n"
            "\n"
            "         docker run -d --name kuma-v1-conditions -p 3023:3001 \\\n"
            "             louislam/uptime-kuma:1.23.2\n"
            "\n"
            "       Then set UPTIME_KUMA_V1_URL, UPTIME_KUMA_V1_USERNAME and\n"
            "       UPTIME_KUMA_V1_PASSWORD in the environment or tests/.env.\n"
            "       UPTIME_KUMA_URL is deliberately NOT used: that key points at\n"
            "       the 2.x instance the other live_test_* scripts target."
        )

    username = os.environ.get("UPTIME_KUMA_V1_USERNAME")
    password = os.environ.get("UPTIME_KUMA_V1_PASSWORD")
    missing = [
        name
        for name, value in (
            ("UPTIME_KUMA_V1_USERNAME", username),
            ("UPTIME_KUMA_V1_PASSWORD", password),
        )
        if not value
    ]
    if missing:
        raise SystemExit(
            f"ABORT: {', '.join(missing)} not set.\n"
            "       A fresh container is bootstrapped with these credentials via\n"
            "       need_setup() / setup(); an already-initialised one is logged\n"
            "       into with them. Uptime Kuma requires at least 6 characters."
        )

    return url, username, password


def bootstrap(api: UptimeKumaApi, username: str, password: str) -> None:
    """Create the admin account if the container is fresh, then log in."""
    if api.need_setup():
        api.setup(username, password)
        record("setup() bootstrapped the fresh container", True,
               "credentials taken from UPTIME_KUMA_V1_USERNAME / _PASSWORD")
    else:
        record("container already set up, skipping setup()", True)

    api.login(username, password)
    record("login", True, f"server reports version {api.version}")


def guard_server_is_v1(api: UptimeKumaApi) -> None:
    """Refuse to continue unless the server really is a 1.23.x instance.

    Every check below is about v1 behaviour, so running them against a 2.x
    server would report a meaningless all-PASS. This also catches a mistargeted
    URL before anything is created.
    """
    version = api.version
    if not str(version).startswith(REQUIRED_VERSION_PREFIX):
        # main()'s finally block disconnects, so do not disconnect here as well.
        raise SystemExit(
            f"ABORT: the server reports version {version}, but this script only\n"
            f"       makes sense against Uptime Kuma {REQUIRED_VERSION_PREFIX}.x.\n"
            "       Nothing was created. Check UPTIME_KUMA_V1_URL -- it must point\n"
            "       at the disposable 1.23.x container, not at a 2.x instance."
        )
    record(f"server version starts with {REQUIRED_VERSION_PREFIX}", True,
           f"version {version}")


def add_monitor_checked(api: UptimeKumaApi, label: str, sent: dict,
                        created: list):
    """Create a monitor, record the result, and round-trip it.

    A server-side rejection is recorded as a FAIL rather than allowed to abort
    the run, because the whole point of the script is to report on that call. If
    the regression is present the server answers with
    ``SQLITE_ERROR: table monitor has no column named conditions``, which
    ``_call`` surfaces as ``UptimeKumaException`` -- exactly the failure this
    check exists to catch.

    :return: The new monitor id, or None if the add failed.
    """
    try:
        r = api.add_monitor(**sent)
    except Exception as e:
        record(label, False, f"{type(e).__name__}: {e}")
        return None

    monitor_id = r.get("monitorID")
    if monitor_id is not None:
        created.append(monitor_id)
    record(
        label,
        r.get("msg") == "Added Successfully." and monitor_id is not None,
        f"server response: {r!r}",
    )
    return monitor_id


def expect_conditions_rejected(label: str, call, monitor_ids_before: set,
                               api: UptimeKumaApi) -> None:
    """Assert an explicit `conditions` value raises and creates nothing."""
    try:
        call()
    except UptimeKumaException as e:
        message = str(e)
        names_field = "conditions" in message
        names_version = "2.0" in message
        ok = names_field and names_version
        detail = f"raised UptimeKumaException -> {message}"
        if not ok:
            missing = []
            if not names_field:
                missing.append("the field name 'conditions'")
            if not names_version:
                missing.append("the required version '2.0'")
            detail = (f"message does not name {' and '.join(missing)}: "
                      f"{message}")
        record(label, ok, detail)
    except Exception as e:
        record(label, False,
               f"expected UptimeKumaException, got {type(e).__name__}: {e}")
    else:
        record(label, False,
               "no exception raised -- an explicit conditions value was accepted "
               "on a pre-2.0 server")

    # The guard is supposed to fire before any server call, so nothing may have
    # been created regardless of how the check above went.
    monitor_ids_after = {m["id"] for m in api.get_monitors()}
    new_ids = monitor_ids_after - monitor_ids_before
    record(
        f"{label} -- no monitor was created",
        not new_ids,
        "" if not new_ids else f"unexpected new monitor id(s): {sorted(new_ids)}",
    )


def main() -> int:
    url, username, password = read_config()

    print(f"Target: {url}")
    print("This script CREATES monitors. Disposable v1 containers ONLY.")
    print()

    print(f"Connecting to {url} ...")
    api = UptimeKumaApi(url)

    created = []

    try:
        print()
        print("Step 1: bootstrap and login")
        bootstrap(api, username, password)

        print()
        print("Step 2: the server must be a 1.23.x instance")
        guard_server_is_v1(api)

        print()
        print("Step 3: add_monitor() with no conditions argument -- the "
              "acceptance criterion")
        http_sent = {
            "type": MonitorType.HTTP,
            "name": "v1-conditions-gate",
            "url": "http://127.0.0.1",
        }
        # No conditions kwarg, and no pop("conditions") workaround. This is
        # exactly the call that failed with SQLITE_ERROR before the fix.
        http_id = add_monitor_checked(
            api,
            "add_monitor(type=HTTP) returns 'Added Successfully.' with a monitorID",
            http_sent,
            created,
        )

        print()
        print("Step 4: round-trip the created monitor")
        if http_id is None:
            record("monitor v1-conditions-gate round-trip", False,
                   "the add in step 3 failed, so there is nothing to read back")
        else:
            got = api.get_monitor(http_id)
            check_round_trip(f"monitor v1-conditions-gate (id={http_id})",
                             http_sent, got)
            # A v1 server has no conditions column, so it cannot echo one back.
            # Its absence confirms nothing unsupported was persisted.
            record(
                "v1 server does not return a conditions field",
                "conditions" not in got,
                "" if "conditions" not in got
                else f"UNEXPECTED: conditions present: {got['conditions']!r}",
            )

        print()
        print("Step 5: the same add for a second monitor type (not HTTP-specific)")
        ping_sent = {
            "type": MonitorType.PING,
            "name": "v1-conditions-gate-ping",
            "hostname": "127.0.0.1",
        }
        ping_id = add_monitor_checked(
            api,
            "add_monitor(type=PING) returns 'Added Successfully.' with a monitorID",
            ping_sent,
            created,
        )
        if ping_id is not None:
            check_round_trip(f"monitor v1-conditions-gate-ping (id={ping_id})",
                             ping_sent, api.get_monitor(ping_id))

        print()
        print("Step 6: explicit conditions on add_monitor is rejected")
        ids_before = {m["id"] for m in api.get_monitors()}
        expect_conditions_rejected(
            "add_monitor(conditions=[...]) raises UptimeKumaException",
            lambda: api.add_monitor(
                type=MonitorType.HTTP,
                name="v1-conditions-gate-explicit",
                url="http://127.0.0.1",
                conditions=SAMPLE_CONDITIONS,
            ),
            ids_before,
            api,
        )

        print()
        print("Step 7: edit_monitor() without conditions still works")
        # Steps 7 and 8 both need a monitor that exists, so they depend on
        # step 3 having succeeded.
        edit_target = http_id if http_id is not None else ping_id
        if edit_target is None:
            record("edit_monitor(interval=120) succeeds", False,
                   "no monitor was created, so there is nothing to edit")
        else:
            try:
                r = api.edit_monitor(edit_target, interval=120)
            except Exception as e:
                record(f"edit_monitor({edit_target}, interval=120) succeeds",
                       False, f"{type(e).__name__}: {e}")
            else:
                record(
                    f"edit_monitor({edit_target}, interval=120) succeeds",
                    r.get("msg") == "Saved.",
                    f"server response: {r!r}",
                )
                check_round_trip(f"interval persisted on monitor {edit_target}",
                                 {"interval": 120}, api.get_monitor(edit_target))

        print()
        print("Step 8: explicit conditions on edit_monitor is rejected")
        if edit_target is None:
            record("edit_monitor(conditions=[...]) raises UptimeKumaException",
                   False, "no monitor was created, so there is nothing to edit")
        else:
            ids_before = {m["id"] for m in api.get_monitors()}
            expect_conditions_rejected(
                f"edit_monitor({edit_target}, conditions=[...]) raises "
                "UptimeKumaException",
                lambda: api.edit_monitor(edit_target,
                                         conditions=SAMPLE_CONDITIONS),
                ids_before,
                api,
            )

    finally:
        print()
        print("Cleanup")
        for monitor_id in created:
            try:
                api.delete_monitor(monitor_id)
                print(f"  deleted monitor {monitor_id}")
            except Exception as e:
                print(f"  FAILED to delete monitor {monitor_id}: "
                      f"{type(e).__name__}: {e}")
        if not created:
            print("  nothing to delete (no monitor was created)")
        api.disconnect()
        print("  disconnected")
        print("  the container itself is disposable: docker rm -f kuma-v1-conditions")

    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed

    print()
    print("=" * 60)
    print(f"  {passed} passed, {failed} failed, {len(results)} checks total")
    print("=" * 60)

    if failed:
        print()
        print("Failed checks:")
        for label, ok, detail in results:
            if not ok:
                print(f"  {label}")
                if detail:
                    print(f"    {detail}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
