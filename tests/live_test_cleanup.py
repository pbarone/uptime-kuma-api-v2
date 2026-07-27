"""
Live integration test — CLEANUP phase.

Removes the resources created by live_test_create.py from the live Uptime Kuma
instance.

Deletion targets two overlapping sets:
  1. IDs recorded in tests/.live_test_ids.json during creation
  2. anything named with the "[TEST] " prefix

The prefix sweep exists to catch orphans when the creation script fails partway
through. It means this script will delete ANY resource whose name starts with
"[TEST] ", including resources it did not create. Check the plan it prints
before confirming if that matters to you.

Output is deliberately ASCII only. The Windows console defaults to cp1252 and
raises UnicodeEncodeError on characters like check marks, which previously
crashed this script before it deleted anything.

Configuration:
    Create a tests/.env file with:
        UPTIME_KUMA_URL=http://your-host:3001/
        UPTIME_KUMA_USERNAME=admin
        UPTIME_KUMA_PASSWORD=your-password

Usage:
    .venv/Scripts/python tests/live_test_cleanup.py
    .venv/Scripts/python tests/live_test_cleanup.py --dry-run
"""
import argparse
import json
import os
import sys

sys.path.insert(0, ".")

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from uptime_kuma_api import UptimeKumaApi

PREFIX = "[TEST] "
IDS_FILE = os.path.join("tests", ".live_test_ids.json")


def load_saved_ids() -> dict:
    saved = {"monitors": [], "notifications": [], "status_pages": []}
    if not os.path.exists(IDS_FILE):
        print(f"  no {IDS_FILE}; falling back to '{PREFIX}' name matching only")
        return saved
    with open(IDS_FILE) as f:
        loaded = json.load(f)
    for key in saved:
        saved[key] = loaded.get(key, [])
    print(f"  loaded IDs from {IDS_FILE}")
    return saved


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove [TEST] resources.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would be deleted without deleting anything",
    )
    args = parser.parse_args()

    try:
        url = os.environ["UPTIME_KUMA_URL"]
        username = os.environ["UPTIME_KUMA_USERNAME"]
        password = os.environ["UPTIME_KUMA_PASSWORD"]
    except KeyError as e:
        raise SystemExit(f"ABORT: {e.args[0]} is not set in tests/.env")

    print(f"Connecting to {url} ...")
    api = UptimeKumaApi(url)
    deleted = {"monitors": 0, "notifications": 0, "status_pages": 0}
    kept = {"monitors": 0, "notifications": 0, "status_pages": 0}
    failures = []

    try:
        api.login(username, password)
        print(f"  connected, server version {api.version}")
        saved = load_saved_ids()
        print()

        if args.dry_run:
            print("DRY RUN - nothing will be deleted")
            print()

        print("Monitors")
        for monitor in api.get_monitors():
            match = monitor["id"] in saved["monitors"] or monitor["name"].startswith(PREFIX)
            if not match:
                kept["monitors"] += 1
                continue
            label = f"id={monitor['id']} name={monitor['name']!r}"
            if args.dry_run:
                print(f"  WOULD DELETE {label}")
                continue
            try:
                api.delete_monitor(monitor["id"])
                deleted["monitors"] += 1
                print(f"  deleted {label}")
            except Exception as e:
                failures.append(f"monitor {label}: {type(e).__name__}: {e}")
                print(f"  FAILED  {label}: {type(e).__name__}")

        print()
        print("Notifications")
        for notification in api.get_notifications():
            name = notification.get("name", "")
            match = notification["id"] in saved["notifications"] or name.startswith(PREFIX)
            if not match:
                kept["notifications"] += 1
                continue
            label = f"id={notification['id']} name={name!r}"
            if args.dry_run:
                print(f"  WOULD DELETE {label}")
                continue
            try:
                api.delete_notification(notification["id"])
                deleted["notifications"] += 1
                print(f"  deleted {label}")
            except Exception as e:
                failures.append(f"notification {label}: {type(e).__name__}: {e}")
                print(f"  FAILED  {label}: {type(e).__name__}")

        print()
        print("Status pages")
        for page in api.get_status_pages():
            slug = page.get("slug")
            title = str(page.get("title", ""))
            match = slug in saved["status_pages"] or title.startswith(PREFIX)
            if not match:
                kept["status_pages"] += 1
                continue
            label = f"slug={slug!r} title={title!r}"
            if args.dry_run:
                print(f"  WOULD DELETE {label}")
                continue
            try:
                api.delete_status_page(slug)
                deleted["status_pages"] += 1
                print(f"  deleted {label}")
            except Exception as e:
                failures.append(f"status page {label}: {type(e).__name__}: {e}")
                print(f"  FAILED  {label}: {type(e).__name__}")

    finally:
        api.disconnect()

    print()
    print("=" * 60)
    if args.dry_run:
        print("  DRY RUN complete - nothing deleted")
    else:
        print(f"  deleted: {deleted['monitors']} monitors, "
              f"{deleted['notifications']} notifications, "
              f"{deleted['status_pages']} status pages")
    print(f"  left untouched: {kept['monitors']} monitors, "
          f"{kept['notifications']} notifications, "
          f"{kept['status_pages']} status pages")
    print("=" * 60)

    if failures:
        print()
        print(f"{len(failures)} deletion(s) failed:")
        for f in failures:
            print(f"  {f}")
        print("Re-run to retry, or remove them in the UI.")
        return 1

    if not args.dry_run and os.path.exists(IDS_FILE):
        os.remove(IDS_FILE)
        print(f"\nremoved {IDS_FILE}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
