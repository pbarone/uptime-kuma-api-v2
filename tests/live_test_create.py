"""
Live integration test — CREATION and VERIFICATION phase.

Connects to a live Uptime Kuma v2 instance, creates one resource for every
feature added in 2.1.0, then reads each one back and compares the fields the
server returned against the fields that were sent.

This round-trip comparison is the point of the script. A server that silently
drops or renames a field looks identical to success from the client side, so
creating a resource without reading it back proves very little.

What a failure means:
    ABSENT     the server did not return the field at all — it was probably
               dropped, ignored, or the library is sending the wrong key
    MISMATCH   the server returned a different value than was sent — likely a
               type or format problem (e.g. sending int where str is expected)

Monitors created here intentionally point at unreachable targets, so they will
show as DOWN in the UI. That is expected. This script tests whether the server
accepts and persists the configuration, not whether the target responds.

Resources are named with a "[TEST] " prefix and their IDs are written to
tests/.live_test_ids.json after each creation, so live_test_cleanup.py can
remove them even if this script fails partway through.

Configuration:
    Create a tests/.env file with:
        UPTIME_KUMA_URL=http://your-host:3001/
        UPTIME_KUMA_USERNAME=admin
        UPTIME_KUMA_PASSWORD=your-password

Usage:
    .venv/Scripts/python tests/live_test_create.py
    .venv/Scripts/python tests/live_test_create.py --allow-default-notifications

Exit code is 0 only if every round-trip check passed.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, ".")

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from packaging.version import parse as parse_version

from uptime_kuma_api import (
    MonitorBuilder,
    MonitorType,
    NotificationType,
    UptimeKumaApi,
)

PREFIX = "[TEST] "
IDS_FILE = os.path.join("tests", ".live_test_ids.json")

created = {"monitors": [], "notifications": [], "status_pages": []}
results = []


def save_ids():
    """Persist created IDs after every creation so cleanup can always recover."""
    os.makedirs(os.path.dirname(IDS_FILE), exist_ok=True)
    with open(IDS_FILE, "w") as f:
        json.dump(created, f, indent=2)


def equivalent(expected, actual) -> bool:
    """
    Compare a sent value against a returned value, tolerating the type coercion
    Uptime Kuma applies on the way through its database.

    Deliberately tolerant about representation (bool as 0/1, numbers as
    strings, lists as JSON strings) and strict about actual value differences.
    """
    if expected == actual:
        return True

    # Uptime Kuma stores booleans as integers in some columns.
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

    # Numbers may come back as strings, or vice versa.
    if isinstance(expected, (int, float)) and isinstance(actual, str):
        try:
            return float(actual) == float(expected)
        except ValueError:
            return False
    if isinstance(expected, str) and isinstance(actual, (int, float)) and not isinstance(actual, bool):
        try:
            return float(expected) == float(actual)
        except ValueError:
            return False

    # Lists are sent JSON-encoded for some fields (e.g. rabbitmqNodes).
    if isinstance(expected, list) and isinstance(actual, str):
        try:
            return json.loads(actual) == expected
        except (ValueError, TypeError):
            return False

    return False


def record(label: str, ok: bool, detail: str = "") -> bool:
    """Record one check result and report it as it happens."""
    results.append((label, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if not ok and detail:
        print(f"          {detail}")
    return ok


def check(label: str, sent: dict, got: dict) -> bool:
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


def check_absent(label: str, key: str, got: dict) -> bool:
    """Verify a field is *not* present, for fields v2 is expected to drop."""
    absent = key not in got
    detail = "" if absent else f"UNEXPECTED: {key} still present: {got[key]!r}"
    return record(label, absent, detail)


def add_monitor(api, label: str, verify: dict, **kwargs) -> int:
    """Create a monitor, register it for cleanup, then verify the round-trip.

    `verify` holds the fields to compare after reading the monitor back. It is
    kept separate from `kwargs` because some sent values are transformed by the
    library before transmission (e.g. rabbitmqNodes is JSON-encoded), so what
    should come back is not always identical to what was passed in.
    """
    r = api.add_monitor(name=f"{PREFIX}{label}", **kwargs)
    monitor_id = r["monitorID"]
    created["monitors"].append(monitor_id)
    save_ids()

    got = api.get_monitor(monitor_id)
    check(f"monitor {label} (id={monitor_id})", verify, got)
    return monitor_id


def add_notification(api, label: str, verify: dict, **kwargs) -> int:
    r = api.add_notification(name=f"{PREFIX}{label}", **kwargs)
    notification_id = r["id"]
    created["notifications"].append(notification_id)
    save_ids()

    got = api.get_notification(notification_id)
    check(f"notification {label} (id={notification_id})", verify, got)
    return notification_id


def preflight(api, allow_default_notifications: bool) -> None:
    """Refuse to run where the results would be meaningless or disruptive."""
    version = api.version
    print(f"  server version: {version}")

    if parse_version(version) < parse_version("2.0"):
        raise SystemExit(
            f"ABORT: this script tests v2-only features but the server is {version}.\n"
            "       Point tests/.env at an Uptime Kuma 2.x instance."
        )

    # Uptime Kuma attaches notifications flagged as default to every new
    # monitor. These monitors are meant to be DOWN, so a default notification
    # would fire an alert for each one.
    defaults = [n for n in api.get_notifications() if n.get("isDefault")]
    if defaults and not allow_default_notifications:
        names = ", ".join(repr(n.get("name")) for n in defaults)
        raise SystemExit(
            f"ABORT: {len(defaults)} default notification(s) found: {names}\n"
            "       Every monitor created here is intentionally unreachable, so these\n"
            "       would send a DOWN alert for each one.\n"
            "       Disable 'Default enabled' on them, or re-run with\n"
            "       --allow-default-notifications to accept the alerts."
        )
    if defaults:
        print(f"  WARNING: {len(defaults)} default notification(s) will fire DOWN alerts")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-default-notifications",
        action="store_true",
        help="proceed even though default notifications will alert on the test monitors",
    )
    args = parser.parse_args()

    try:
        url = os.environ["UPTIME_KUMA_URL"]
        username = os.environ["UPTIME_KUMA_USERNAME"]
        password = os.environ["UPTIME_KUMA_PASSWORD"]
    except KeyError as e:
        raise SystemExit(
            f"ABORT: {e.args[0]} is not set. Create tests/.env with "
            "UPTIME_KUMA_URL, UPTIME_KUMA_USERNAME and UPTIME_KUMA_PASSWORD."
        )

    print(f"Connecting to {url} ...")
    api = UptimeKumaApi(url)

    try:
        api.login(username, password)
        print("  connected")
        preflight(api, args.allow_default_notifications)
        print()

        print("New monitor types")
        add_monitor(
            api, "SMTP Monitor",
            verify={"type": MonitorType.SMTP, "hostname": "smtp.gmail.com",
                    "port": 587, "smtpSecurity": "starttls"},
            type=MonitorType.SMTP, hostname="smtp.gmail.com", port=587,
            smtpSecurity="starttls",
        )
        add_monitor(
            api, "SNMP Monitor",
            verify={"type": MonitorType.SNMP, "hostname": "10.0.0.1", "port": 161,
                    "snmpOid": "1.3.6.1.2.1.1.1.0", "snmpVersion": "2c"},
            type=MonitorType.SNMP, hostname="10.0.0.1", port=161,
            snmpOid="1.3.6.1.2.1.1.1.0", snmpVersion="2c",
        )
        add_monitor(
            api, "RabbitMQ Monitor",
            verify={"type": MonitorType.RABBITMQ,
                    "rabbitmqNodes": ["amqp://localhost:5672"],
                    "rabbitmqUsername": "guest", "rabbitmqPassword": "guest"},
            type=MonitorType.RABBITMQ, rabbitmqNodes=["amqp://localhost:5672"],
            rabbitmqUsername="guest", rabbitmqPassword="guest",
        )
        add_monitor(
            api, "System Service Monitor",
            verify={"type": MonitorType.SYSTEM_SERVICE, "system_service_name": "nginx"},
            type=MonitorType.SYSTEM_SERVICE, system_service_name="nginx",
        )

        print()
        print("v2 monitor parameters")
        add_monitor(
            api, "HTTP v2 Params",
            verify={"url": "https://httpbin.org/get", "ipFamily": "IPv4",
                    "cacheBust": True, "saveResponse": True,
                    "saveErrorResponse": True, "responseMaxLength": 5000,
                    "domainExpiryNotification": True},
            type=MonitorType.HTTP, url="https://httpbin.org/get", ipFamily="IPv4",
            cacheBust=True, saveResponse=True, saveErrorResponse=True,
            responseMaxLength=5000, domainExpiryNotification=True,
        )
        add_monitor(
            api, "JSON Query Operator",
            verify={"jsonPath": "$.slideshow.title", "expectedValue": "Sample",
                    "jsonPathOperator": "contains"},
            type=MonitorType.JSON_QUERY, url="https://httpbin.org/json",
            jsonPath="$.slideshow.title", expectedValue="Sample",
            jsonPathOperator="contains",
        )
        add_monitor(
            api, "PING v2 Params",
            verify={"hostname": "8.8.8.8", "ping_count": 3, "ping_numeric": True},
            type=MonitorType.PING, hostname="8.8.8.8", ping_count=3,
            ping_numeric=True,
        )

        print()
        print("MonitorBuilder end-to-end")
        config = (
            MonitorBuilder()
            .type(MonitorType.HTTP)
            .name(f"{PREFIX}MonitorBuilder Test")
            .url("https://example.com")
            .interval(120)
            .conditions([
                {"type": "expression", "variable": "response_status",
                 "operator": "==", "value": "200", "andOr": ""}
            ])
            .build()
        )
        r = api.add_monitor(**config)
        builder_id = r["monitorID"]
        created["monitors"].append(builder_id)
        save_ids()
        got = api.get_monitor(builder_id)
        check(
            f"monitor MonitorBuilder Test (id={builder_id})",
            {"url": "https://example.com", "interval": 120},
            got,
        )

        print()
        print("New notification providers")
        add_notification(
            api, "Brevo Notification",
            verify={"type": NotificationType.BREVO,
                    "brevoApiKey": "xkeysib-test-key-12345",
                    "brevoFromEmail": "test@example.com",
                    "brevoToEmail": "recipient@example.com"},
            type=NotificationType.BREVO,
            brevoApiKey="xkeysib-test-key-12345",
            brevoFromEmail="test@example.com",
            brevoToEmail="recipient@example.com",
        )
        add_notification(
            api, "Evolution API Notification",
            verify={"type": NotificationType.EVOLUTION_API,
                    "evolutionInstanceName": "test-instance",
                    "evolutionAuthToken": "test-token-123",
                    "evolutionRecipient": "5511999999999"},
            type=NotificationType.EVOLUTION_API,
            evolutionInstanceName="test-instance",
            evolutionAuthToken="test-token-123",
            evolutionRecipient="5511999999999",
        )
        add_notification(
            api, "Nextcloud Talk Notification",
            verify={"type": NotificationType.NEXTCLOUD_TALK,
                    "host": "https://nextcloud.example.com",
                    "conversationToken": "test-token",
                    "botSecret": "test-secret"},
            type=NotificationType.NEXTCLOUD_TALK,
            host="https://nextcloud.example.com",
            conversationToken="test-token",
            botSecret="test-secret",
        )

        print()
        print("Status page with v2 analytics")
        slug = "test-v2-analytics"
        api.add_status_page(slug, f"{PREFIX}Status Page v2")
        created["status_pages"].append(slug)
        save_ids()
        api.save_status_page(
            slug=slug,
            title=f"{PREFIX}Status Page v2",
            analyticsType="plausible",
            analyticsId="test-domain.example.com",
            analyticsScriptUrl="https://plausible.io/js/script.js",
            showOnlyLastHeartbeat=True,
            rssTitle="Test RSS Feed",
        )
        got = api.get_status_page(slug)
        check(
            f"status page v2 analytics (slug={slug})",
            {"analyticsType": "plausible",
             "analyticsId": "test-domain.example.com",
             "analyticsScriptUrl": "https://plausible.io/js/script.js",
             "showOnlyLastHeartbeat": True,
             "rssTitle": "Test RSS Feed"},
            got,
        )
        # v2 replaced googleAnalyticsId with the analytics* fields, so its
        # continued absence is part of the contract.
        check_absent(
            "status page omits v1 googleAnalyticsId on v2",
            "googleAnalyticsId",
            got,
        )

    finally:
        api.disconnect()

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
                print(f"    {detail}")

    print()
    print("Created resources:")
    print(f"  monitors:      {created['monitors']}")
    print(f"  notifications: {created['notifications']}")
    print(f"  status pages:  {created['status_pages']}")
    print()
    print(f"Inspect them at {os.environ['UPTIME_KUMA_URL']}")
    print("Then clean up:  .venv\\Scripts\\python tests/live_test_cleanup.py")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
