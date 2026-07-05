"""
Live integration test — CLEANUP phase.

Connects to the live Uptime Kuma v2 instance and removes all test
resources created by `live_test_create.py`.

Reads resource IDs from `tests/.live_test_ids.json` (saved by the
creation script). Also scans for any [TEST]-prefixed resources that
might have been missed.

Configuration:
    Create a `tests/.env` file with:
        UPTIME_KUMA_URL=http://your-host:3001/
        UPTIME_KUMA_USERNAME=admin
        UPTIME_KUMA_PASSWORD=your-password

Usage:
    .venv/Scripts/python tests/live_test_cleanup.py
"""
import os
import sys
import json

sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from uptime_kuma_api import UptimeKumaApi

URL = os.environ["UPTIME_KUMA_URL"]
USERNAME = os.environ["UPTIME_KUMA_USERNAME"]
PASSWORD = os.environ["UPTIME_KUMA_PASSWORD"]

PREFIX = "[TEST] "
IDS_FILE = "tests/.live_test_ids.json"


def main():
    print(f"Connecting to {URL}...")
    api = UptimeKumaApi(URL)

    try:
        api.login(USERNAME, PASSWORD)
        print(f"✓ Connected. Server version: {api.version}")
        print()

        # Load saved IDs if available
        saved_ids = {"monitors": [], "notifications": [], "status_pages": []}
        if os.path.exists(IDS_FILE):
            with open(IDS_FILE, "r") as f:
                saved_ids = json.load(f)
            print(f"  Loaded saved IDs from {IDS_FILE}")
        else:
            print(f"  No saved IDs file found — will scan for [TEST] prefixed resources")

        deleted = {"monitors": 0, "notifications": 0, "status_pages": 0}

        # ═══════════════════════════════════════════════════════════════════
        # 1. Delete monitors (by saved ID + scan for [TEST] prefix)
        # ═══════════════════════════════════════════════════════════════════
        print()
        print("─── Cleaning up monitors ───")

        monitors = api.get_monitors()
        for monitor in monitors:
            should_delete = (
                monitor["id"] in saved_ids["monitors"]
                or monitor["name"].startswith(PREFIX)
            )
            if should_delete:
                api.delete_monitor(monitor["id"])
                print(f"  ✗ Deleted monitor: id={monitor['id']} name={monitor['name']}")
                deleted["monitors"] += 1

        # ═══════════════════════════════════════════════════════════════════
        # 2. Delete notifications (by saved ID + scan for [TEST] prefix)
        # ═══════════════════════════════════════════════════════════════════
        print()
        print("─── Cleaning up notifications ───")

        notifications = api.get_notifications()
        for notification in notifications:
            should_delete = (
                notification["id"] in saved_ids["notifications"]
                or notification["name"].startswith(PREFIX)
            )
            if should_delete:
                api.delete_notification(notification["id"])
                print(f"  ✗ Deleted notification: id={notification['id']} name={notification['name']}")
                deleted["notifications"] += 1

        # ═══════════════════════════════════════════════════════════════════
        # 3. Delete status pages (by saved slug + scan for [TEST] prefix)
        # ═══════════════════════════════════════════════════════════════════
        print()
        print("─── Cleaning up status pages ───")

        status_pages = api.get_status_pages()
        for sp in status_pages:
            should_delete = (
                sp["slug"] in saved_ids["status_pages"]
                or sp.get("title", "").startswith(PREFIX)
            )
            if should_delete:
                api.delete_status_page(sp["slug"])
                print(f"  ✗ Deleted status page: slug={sp['slug']} title={sp.get('title', '?')}")
                deleted["status_pages"] += 1

        # ═══════════════════════════════════════════════════════════════════
        # Summary
        # ═══════════════════════════════════════════════════════════════════
        print()
        print("═══════════════════════════════════════════════════")
        print("  CLEANUP COMPLETE")
        print("═══════════════════════════════════════════════════")
        print(f"  Monitors deleted:      {deleted['monitors']}")
        print(f"  Notifications deleted: {deleted['notifications']}")
        print(f"  Status pages deleted:  {deleted['status_pages']}")

        # Remove the IDs file
        if os.path.exists(IDS_FILE):
            os.remove(IDS_FILE)
            print(f"  Removed {IDS_FILE}")

    finally:
        api.disconnect()


if __name__ == "__main__":
    main()
