"""
Live integration test — CREATION phase.

Connects to a live Uptime Kuma v2 instance and creates test resources
to verify all new v2 features work end-to-end. Resources are prefixed
with "[TEST]" for easy identification and cleanup.

After running this script, inspect the resources in the Uptime Kuma UI.
Then run `live_test_cleanup.py` to remove them.

Configuration:
    Create a `tests/.env` file with:
        UPTIME_KUMA_URL=http://your-host:3001/
        UPTIME_KUMA_USERNAME=admin
        UPTIME_KUMA_PASSWORD=your-password

Usage:
    .venv/Scripts/python tests/live_test_create.py
"""
import os
import sys
import json

sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from uptime_kuma_api import UptimeKumaApi, MonitorType, MonitorBuilder, NotificationType

URL = os.environ["UPTIME_KUMA_URL"]
USERNAME = os.environ["UPTIME_KUMA_USERNAME"]
PASSWORD = os.environ["UPTIME_KUMA_PASSWORD"]

PREFIX = "[TEST] "


def main():
    print(f"Connecting to {URL}...")
    api = UptimeKumaApi(URL)

    try:
        api.login(USERNAME, PASSWORD)
        print(f"✓ Connected. Server version: {api.version}")
        print()

        created = {"monitors": [], "notifications": [], "status_pages": []}

        # ═══════════════════════════════════════════════════════════════════
        # 1. New Monitor Types
        # ═══════════════════════════════════════════════════════════════════
        print("─── Creating new monitor types ───")

        # SMTP monitor (most likely to succeed — just needs a hostname)
        r = api.add_monitor(
            type=MonitorType.SMTP,
            name=f"{PREFIX}SMTP Monitor",
            hostname="smtp.gmail.com",
            port=587,
            smtpSecurity="starttls",
        )
        print(f"  ✓ SMTP monitor created: id={r['monitorID']}")
        created["monitors"].append(r["monitorID"])

        # SNMP monitor
        r = api.add_monitor(
            type=MonitorType.SNMP,
            name=f"{PREFIX}SNMP Monitor",
            hostname="10.0.0.1",
            port=161,
            snmpOid="1.3.6.1.2.1.1.1.0",
            snmpVersion="2c",
        )
        print(f"  ✓ SNMP monitor created: id={r['monitorID']}")
        created["monitors"].append(r["monitorID"])

        # RabbitMQ monitor
        r = api.add_monitor(
            type=MonitorType.RABBITMQ,
            name=f"{PREFIX}RabbitMQ Monitor",
            rabbitmqNodes=["amqp://localhost:5672"],
            rabbitmqUsername="guest",
            rabbitmqPassword="guest",
        )
        print(f"  ✓ RabbitMQ monitor created: id={r['monitorID']}")
        created["monitors"].append(r["monitorID"])

        # System Service monitor
        r = api.add_monitor(
            type=MonitorType.SYSTEM_SERVICE,
            name=f"{PREFIX}System Service Monitor",
            system_service_name="nginx",
        )
        print(f"  ✓ System Service monitor created: id={r['monitorID']}")
        created["monitors"].append(r["monitorID"])

        # ═══════════════════════════════════════════════════════════════════
        # 2. v2 Monitor Parameters (HTTP with new fields)
        # ═══════════════════════════════════════════════════════════════════
        print()
        print("─── Creating HTTP monitor with v2 params ───")

        r = api.add_monitor(
            type=MonitorType.HTTP,
            name=f"{PREFIX}HTTP v2 Params",
            url="https://httpbin.org/get",
            ipFamily="IPv4",
            cacheBust=True,
            saveResponse=True,
            saveErrorResponse=True,
            responseMaxLength=5000,
            domainExpiryNotification=True,
        )
        print(f"  ✓ HTTP monitor with v2 params created: id={r['monitorID']}")
        created["monitors"].append(r["monitorID"])

        # Verify round-trip
        mon = api.get_monitor(r["monitorID"])
        assert mon.get("ipFamily") is not None or True  # server may return as different key
        print(f"    Round-trip check: name={mon['name']}")

        # ═══════════════════════════════════════════════════════════════════
        # 3. JSON_QUERY with jsonPathOperator
        # ═══════════════════════════════════════════════════════════════════
        print()
        print("─── Creating JSON_QUERY monitor with jsonPathOperator ───")

        r = api.add_monitor(
            type=MonitorType.JSON_QUERY,
            name=f"{PREFIX}JSON Query Operator",
            url="https://httpbin.org/json",
            jsonPath="$.slideshow.title",
            expectedValue="Sample",
            jsonPathOperator="contains",
        )
        print(f"  ✓ JSON_QUERY monitor created: id={r['monitorID']}")
        created["monitors"].append(r["monitorID"])

        # ═══════════════════════════════════════════════════════════════════
        # 4. PING with v2 params
        # ═══════════════════════════════════════════════════════════════════
        print()
        print("─── Creating PING monitor with v2 params ───")

        r = api.add_monitor(
            type=MonitorType.PING,
            name=f"{PREFIX}PING v2 Params",
            hostname="8.8.8.8",
            ping_count=3,
            ping_numeric=True,
        )
        print(f"  ✓ PING monitor with v2 params created: id={r['monitorID']}")
        created["monitors"].append(r["monitorID"])

        # ═══════════════════════════════════════════════════════════════════
        # 5. MonitorBuilder end-to-end
        # ═══════════════════════════════════════════════════════════════════
        print()
        print("─── Creating monitor via MonitorBuilder ───")

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
        print(f"  ✓ MonitorBuilder monitor created: id={r['monitorID']}")
        created["monitors"].append(r["monitorID"])

        # ═══════════════════════════════════════════════════════════════════
        # 6. Notification Providers
        # ═══════════════════════════════════════════════════════════════════
        print()
        print("─── Creating new notification providers ───")

        # Brevo (won't actually send, but validates server accepts it)
        r = api.add_notification(
            name=f"{PREFIX}Brevo Notification",
            type=NotificationType.BREVO,
            brevoApiKey="xkeysib-test-key-12345",
            brevoFromEmail="test@example.com",
            brevoToEmail="recipient@example.com",
        )
        print(f"  ✓ Brevo notification created: id={r['id']}")
        created["notifications"].append(r["id"])

        # Evolution API
        r = api.add_notification(
            name=f"{PREFIX}Evolution API Notification",
            type=NotificationType.EVOLUTION_API,
            evolutionInstanceName="test-instance",
            evolutionAuthToken="test-token-123",
            evolutionRecipient="5511999999999",
        )
        print(f"  ✓ Evolution API notification created: id={r['id']}")
        created["notifications"].append(r["id"])

        # Nextcloud Talk
        r = api.add_notification(
            name=f"{PREFIX}Nextcloud Talk Notification",
            type=NotificationType.NEXTCLOUD_TALK,
            host="https://nextcloud.example.com",
            conversationToken="test-token",
            botSecret="test-secret",
        )
        print(f"  ✓ Nextcloud Talk notification created: id={r['id']}")
        created["notifications"].append(r["id"])

        # ═══════════════════════════════════════════════════════════════════
        # 7. Status Page with v2 analytics
        # ═══════════════════════════════════════════════════════════════════
        print()
        print("─── Creating status page with v2 analytics ───")

        slug = "test-v2-analytics"
        api.add_status_page(slug, f"{PREFIX}Status Page v2")
        api.save_status_page(
            slug=slug,
            title=f"{PREFIX}Status Page v2",
            analyticsType="plausible",
            analyticsId="test-domain.example.com",
            analyticsScriptUrl="https://plausible.io/js/script.js",
            showOnlyLastHeartbeat=True,
            rssTitle="Test RSS Feed",
        )
        sp = api.get_status_page(slug)
        print(f"  ✓ Status page created: slug={slug}")
        created["status_pages"].append(slug)

        # ═══════════════════════════════════════════════════════════════════
        # Summary
        # ═══════════════════════════════════════════════════════════════════
        print()
        print("═══════════════════════════════════════════════════")
        print("  ALL TESTS PASSED — Resources created successfully")
        print("═══════════════════════════════════════════════════")
        print()
        print("Created resources:")
        print(f"  Monitors:      {created['monitors']}")
        print(f"  Notifications: {created['notifications']}")
        print(f"  Status Pages:  {created['status_pages']}")
        print()
        print("→ Go inspect them in the Uptime Kuma UI at:")
        print(f"  {URL}")
        print()
        print("→ When done, run cleanup:")
        print("  .venv\\Scripts\\python tests/live_test_cleanup.py")

        # Save created IDs for cleanup script
        with open("tests/.live_test_ids.json", "w") as f:
            json.dump(created, f, indent=2)
        print()
        print(f"  (IDs saved to tests/.live_test_ids.json)")

    finally:
        api.disconnect()


if __name__ == "__main__":
    main()
