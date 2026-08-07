"""
Verification_Run for the v2-only monitor fields rule -- issue #14, requirement 7.

Not a pytest test. The filename deliberately starts with ``live_test_`` rather
than ``test_``: pytest's default discovery collects ``test_*.py`` and
``*_test.py``, so this prefix keeps the script out of every pytest run,
including a bare ``pytest``. Do not rename it. CI is unaffected by this file,
and ``scripts/check_sdist.py`` keeps it out of the published artifact.

SAFETY -- READ FIRST:
    This script CREATES monitors. Point it ONLY at a disposable, throwaway
    Uptime Kuma 1.23.x container that holds nothing you care about.

    It deliberately does NOT read the ``UPTIME_KUMA_URL`` key the 2.x
    live_test_* scripts use, so it cannot accidentally hit the 2.x instance
    those target. It reads its own ``UPTIME_KUMA_V1_*`` keys and refuses to run
    if the URL is unset -- there is no default.

    A second guard follows: the server must report a version starting with
    ``1.23``, or the run aborts before creating anything.

What this answers, and why it runs BEFORE the code:
    The library gates 26 monitor fields behind a ``>= 2.0`` comparison and
    withholds them on a pre-2.0 server. Whether a 1.x server actually rejects
    each one was never verified -- it was assumed. A field a 1.23.x server
    ACCEPTS and round-trips is not a v2-only field at all, and gating it
    withholds a value the caller could have sent.

    So this run exists to find MIS-GATED fields, and its results decide the
    contents of the Field_Registry (requirement 7.2). Building the registry
    first and pruning it afterwards would ship a warning about a field the
    server would have taken.

How a gated field is put on the wire:
    It cannot go through ``add_monitor``, because that is the code doing the
    gating -- on a 1.23.x server every one of these fields is withheld before
    the payload is built. The probe therefore mirrors ``add_monitor``'s own
    sequence::

        data = api._build_monitor_data(**base)   # v1-safe payload, gated fields absent
        _convert_monitor_input(data)
        _check_arguments_monitor(data)
        data[field] = value                      # inject exactly one gated field
        api._call('add', data)

    One field per monitor, deliberately. A rejected insert names a single
    column, and one bad column fails the whole statement, so probing several at
    once would attribute one rejection to all of them.

Verdicts (requirement 7.1), one per field:
    REJECTED   the server returned an error for the payload carrying the field
    ACCEPTED   the field came back on read-back holding the value sent
    ABSENT     the payload succeeded and the field did not come back
    MISMATCH   the field came back holding a value other than the one sent
    NOT_OBSERVED  the field was never exercised (an incomplete run must read as
                  incomplete, requirement 7.10)

    ACCEPTED is the interesting one: it means the field is mis-gated.
    REJECTED and ABSENT both confirm the gate is correct, for different
    reasons -- the server refuses the column, or silently discards it.

Output is ASCII only. The Windows console defaults to cp1252 and raises
UnicodeEncodeError on check marks, box-drawing characters and arrows, which has
crashed a script mid-run before. Use PASS / FAIL / ->.

Configuration:
    Start a disposable container, for example::

        docker run -d --name kuma-v1-fields -p 3023:3001 louislam/uptime-kuma:1.23.2

    Then set these keys (in the environment or in tests/.env). They are
    referenced by name only; values are never printed by this script:

        UPTIME_KUMA_V1_URL=http://your-disposable-host:3023/
        UPTIME_KUMA_V1_USERNAME=admin
        UPTIME_KUMA_V1_PASSWORD=a-throwaway-password

    A fresh container has no admin user, so the script bootstraps it itself:
    ``need_setup()`` -> ``setup(username, password)`` -> ``login(...)``. Uptime
    Kuma requires a password of at least 6 characters.

    Teardown destroys all state, since the container runs without a volume::

        docker rm -f kuma-v1-fields

Usage:
    .venv/Scripts/python tests/live_test_v2_only_fields_v1.py

Exit code is 0 when the run completed and every field reached a verdict. A
mis-gated (ACCEPTED) field does not fail the run -- it is a finding, and the
summary reports it as one.
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
from uptime_kuma_api.api import (
    _check_arguments_monitor,
    _convert_monitor_input,
)

REQUIRED_VERSION_PREFIX = "1.23"

REJECTED = "REJECTED"
ACCEPTED = "ACCEPTED"
ABSENT = "ABSENT"
MISMATCH = "MISMATCH"
NOT_OBSERVED = "NOT_OBSERVED"

# Minimal valid base payloads, per monitor type. Each is what the library sends
# for that type on a 1.23.x server with no v2-only field involved.
BASE = {
    MonitorType.HTTP: {
        "type": MonitorType.HTTP,
        "url": "http://127.0.0.1",
    },
    MonitorType.JSON_QUERY: {
        "type": MonitorType.JSON_QUERY,
        "url": "http://127.0.0.1",
        "jsonPath": "$.ok",
        "expectedValue": "1",
    },
    MonitorType.PING: {
        "type": MonitorType.PING,
        "hostname": "127.0.0.1",
    },
    MonitorType.MQTT: {
        "type": MonitorType.MQTT,
        "hostname": "127.0.0.1",
        "port": 1883,
        "mqttTopic": "probe/topic",
    },
}

# The 25 Reachable_On_V1 v2-only monitor fields, each with a monitor type it
# applies to and a plausible value. snmp_v3_username is deliberately absent: the
# SNMP monitor type is itself v2-only and the 2.3.1 type gate rejects it before
# any payload is built, so no caller can reach that field on a pre-2.0 server.
#
# Order follows the five groups in the requirements table, so the results file
# reads in the same order as the spec.
FIELDS = [
    # conditions -- the one field that already raises on v1
    ("conditions", MonitorType.HTTP, [
        {
            "type": "expression",
            "variable": "response_status",
            "operator": "==",
            "value": "200",
            "andOr": "",
        }
    ]),

    # network
    ("ipFamily", MonitorType.HTTP, "ipv4"),

    # HTTP set
    ("cacheBust", MonitorType.HTTP, True),
    ("retryOnlyOnStatusCodeFailure", MonitorType.HTTP, True),
    ("bearer_token", MonitorType.HTTP, "probe-token"),
    ("oauth_audience", MonitorType.HTTP, "probe-audience"),
    ("domainExpiryNotification", MonitorType.HTTP, True),
    ("saveResponse", MonitorType.HTTP, True),
    ("saveErrorResponse", MonitorType.HTTP, True),
    ("responseMaxLength", MonitorType.HTTP, 1000),
    ("responsecheck", MonitorType.HTTP, "probe-responsecheck"),

    # low-priority set, no monitor-type restriction
    ("subtype", MonitorType.HTTP, "probe-subtype"),
    ("wsSubprotocol", MonitorType.HTTP, "probe-subprotocol"),
    ("wsIgnoreSecWebsocketAcceptHeader", MonitorType.HTTP, True),
    ("remoteBrowsersToggle", MonitorType.HTTP, True),
    ("remote_browser", MonitorType.HTTP, "probe-remote-browser"),
    ("screenshot_delay", MonitorType.HTTP, 5),
    ("gamedigToken", MonitorType.HTTP, "probe-gamedig-token"),
    ("protocol", MonitorType.HTTP, "https"),

    # gated in place, inside type blocks
    ("jsonPathOperator", MonitorType.JSON_QUERY, "=="),
    ("ping_count", MonitorType.PING, 3),
    ("ping_numeric", MonitorType.PING, True),
    ("ping_per_request_timeout", MonitorType.PING, 5),
    ("mqttWebsocketPath", MonitorType.MQTT, "/mqtt"),
    ("mqttCheckType", MonitorType.MQTT, "keyword"),
]

# field -> (verdict, detail, monitor type used)
verdicts = {name: (NOT_OBSERVED, "", str(type_)) for name, type_, _ in FIELDS}


def equivalent(expected, actual) -> bool:
    """
    Compare a sent value against a returned value, tolerating the type coercion
    Uptime Kuma applies on the way through its database.

    Deliberately tolerant about representation (bool as 0/1, numbers as
    strings, lists as JSON strings) and strict about actual value differences.
    Same helper as live_test_create.py and live_test_conditions_v1.py, kept
    local so this script stands alone.
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
            "         docker run -d --name kuma-v1-fields -p 3023:3001 \\\n"
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
        print("  setup() bootstrapped the fresh container")
    else:
        print("  container already set up, skipping setup()")
    api.login(username, password)
    print(f"  login OK -> server reports version {api.version}")


def guard_server_is_v1(api: UptimeKumaApi) -> None:
    """Refuse to continue unless the server really is a 1.23.x instance.

    Every probe below is about v1 behaviour, so running them against a 2.x
    server would report a meaningless all-ACCEPTED. This also catches a
    mistargeted URL before anything is created.
    """
    version = api.version
    if not str(version).startswith(REQUIRED_VERSION_PREFIX):
        # main()'s finally block disconnects, so do not disconnect here as well.
        raise SystemExit(
            f"ABORT: the server reports version {version}, but this run only\n"
            f"       makes sense against Uptime Kuma {REQUIRED_VERSION_PREFIX}.x.\n"
            "       Nothing was created. Check UPTIME_KUMA_V1_URL -- it must point\n"
            "       at the disposable 1.23.x container, not at a 2.x instance."
        )
    print(f"  PASS  server version starts with {REQUIRED_VERSION_PREFIX} "
          f"({version})")


def build_v1_payload(api: UptimeKumaApi, name: str, base: dict) -> dict:
    """Assemble the payload add_monitor would send, with no v2-only field in it.

    Mirrors add_monitor's own sequence so the probe differs from a real call in
    exactly one respect: the single injected field.
    """
    data = api._build_monitor_data(name=name, **base)
    _convert_monitor_input(data)
    _check_arguments_monitor(data)
    return data


def probe(api: UptimeKumaApi, field: str, type_, value, index: int,
          created: list) -> None:
    """Put one gated field on the wire and record the server's verdict."""
    name = f"v1-fields-probe-{index:02d}-{field}"[:150]
    label = f"{field} ({type_})"

    try:
        data = build_v1_payload(api, name, BASE[type_])
    except Exception as e:
        verdicts[field] = (NOT_OBSERVED,
                           f"could not build a base payload: "
                           f"{type(e).__name__}: {e}", str(type_))
        print(f"  {NOT_OBSERVED:<12} {label} -> base payload failed")
        return

    # The whole point: this key is absent from the payload the library builds on
    # a 1.23.x server, and the probe puts it back.
    data[field] = value

    try:
        r = api._call("add", data)
    except UptimeKumaException as e:
        verdicts[field] = (REJECTED, str(e), str(type_))
        print(f"  {REJECTED:<12} {label}")
        print(f"               -> {e}")
        return
    except Exception as e:
        verdicts[field] = (NOT_OBSERVED,
                           f"unexpected {type(e).__name__}: {e}", str(type_))
        print(f"  {NOT_OBSERVED:<12} {label} -> {type(e).__name__}: {e}")
        return

    monitor_id = r.get("monitorID")
    if monitor_id is None:
        verdicts[field] = (NOT_OBSERVED,
                           f"add returned no monitorID: {r!r}", str(type_))
        print(f"  {NOT_OBSERVED:<12} {label} -> no monitorID in {r!r}")
        return
    created.append(monitor_id)

    try:
        got = api.get_monitor(monitor_id)
    except Exception as e:
        verdicts[field] = (NOT_OBSERVED,
                           f"could not read the monitor back: "
                           f"{type(e).__name__}: {e}", str(type_))
        print(f"  {NOT_OBSERVED:<12} {label} -> read-back failed")
        return

    if field not in got:
        verdicts[field] = (ABSENT,
                           "the add succeeded and the field did not come back",
                           str(type_))
        print(f"  {ABSENT:<12} {label} (id={monitor_id})")
        return

    returned = got[field]
    if equivalent(value, returned):
        verdicts[field] = (ACCEPTED,
                           f"sent {value!r}, got {returned!r}", str(type_))
        print(f"  {ACCEPTED:<12} {label} (id={monitor_id})  "
              f"MIS-GATED: sent {value!r}, got {returned!r}")
    else:
        verdicts[field] = (MISMATCH,
                           f"sent {value!r}, got {returned!r}", str(type_))
        print(f"  {MISMATCH:<12} {label} (id={monitor_id})  "
              f"sent {value!r}, got {returned!r}")


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
        observed_version = api.version

        print()
        print(f"Step 3: probe {len(FIELDS)} v2-only fields, one per monitor")
        for index, (field, type_, value) in enumerate(FIELDS, start=1):
            probe(api, field, type_, value, index, created)

    finally:
        print()
        print("Cleanup")
        for monitor_id in created:
            try:
                api.delete_monitor(monitor_id)
            except Exception as e:
                print(f"  FAILED to delete monitor {monitor_id}: "
                      f"{type(e).__name__}: {e}")
        print(f"  deleted {len(created)} monitor(s)")
        api.disconnect()
        print("  disconnected")
        print("  the container itself is disposable: "
              "docker rm -f kuma-v1-fields")

    counts = {}
    for verdict, _, _ in verdicts.values():
        counts[verdict] = counts.get(verdict, 0) + 1

    print()
    print("=" * 68)
    print(f"  server {observed_version}, {len(FIELDS)} fields probed")
    for verdict in (REJECTED, ABSENT, MISMATCH, ACCEPTED, NOT_OBSERVED):
        if counts.get(verdict):
            print(f"    {verdict:<13} {counts[verdict]}")
    print("=" * 68)

    mis_gated = [f for f, (v, _, _) in verdicts.items() if v == ACCEPTED]
    if mis_gated:
        print()
        print("MIS-GATED -- a 1.23.x server accepted and returned these, so they")
        print("are not v2-only and must be left OUT of the Field_Registry:")
        for field in mis_gated:
            print(f"  {field}")

    unobserved = [f for f, (v, _, _) in verdicts.items() if v == NOT_OBSERVED]
    if unobserved:
        print()
        print("NOT OBSERVED -- this run is incomplete for:")
        for field in unobserved:
            print(f"  {field}  {verdicts[field][1]}")

    print()
    print("Verdict table, for the results file:")
    print()
    print("| Field | Monitor type | Verdict |")
    print("|---|---|---|")
    for field, type_, _ in FIELDS:
        verdict, _, type_name = verdicts[field]
        print(f"| `{field}` | {type_name} | `{verdict}` |")

    return 1 if unobserved else 0


if __name__ == "__main__":
    sys.exit(main())
