"""
Export the full configuration of a live Uptime Kuma instance to a local JSON file.

Read-only. Creates and modifies nothing on the server.

Why this exists: Uptime Kuma has no download-backup endpoint (only
``upload_backup`` for importing its own legacy format), so there is no API call
that produces a real database backup. This script instead walks every read
endpoint and records the result, giving a point-in-time snapshot of what was
configured before a live test run.

SCOPE AND LIMITS — read this before relying on it:
  - This is a *reference snapshot*, not a one-click restore. The format is this
    script's own, not Uptime Kuma's backup format, so ``upload_backup`` will
    not consume it. Restoring means re-creating resources from the recorded
    fields, by hand or by script.
  - Heartbeat/history data is NOT included, only configuration.
  - For a genuinely restorable backup, snapshot the server's SQLite file or
    container volume. See the instructions this script prints on completion.

THE OUTPUT CONTAINS SECRETS: notification API keys, monitor basic-auth
passwords, proxy passwords and API keys are all included in plain text. Files
are written to tests/.backups/, which is gitignored. Do not commit or share them.

Usage:
    .venv/Scripts/python tests/live_test_backup.py
"""
import datetime
import json
import os
import sys

sys.path.insert(0, ".")

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from uptime_kuma_api import UptimeKumaApi

BACKUP_DIR = os.path.join("tests", ".backups")


def main() -> int:
    try:
        url = os.environ["UPTIME_KUMA_URL"]
        username = os.environ["UPTIME_KUMA_USERNAME"]
        password = os.environ["UPTIME_KUMA_PASSWORD"]
    except KeyError as e:
        raise SystemExit(f"ABORT: {e.args[0]} is not set in tests/.env")

    print(f"Connecting to {url} ...")
    api = UptimeKumaApi(url)

    snapshot = {}
    errors = {}

    try:
        api.login(username, password)
        version = api.version
        print(f"  connected, server version {version}")

        snapshot["_meta"] = {
            "exported_at": datetime.datetime.now().astimezone().isoformat(),
            "server_url": url,
            "server_version": version,
            "note": "Configuration snapshot only. No heartbeat history. "
                    "Not restorable via upload_backup.",
        }

        # Each section is fetched independently so one unsupported endpoint
        # cannot abort the whole export.
        sections = {
            "monitors": api.get_monitors,
            "notifications": api.get_notifications,
            "proxies": api.get_proxies,
            "tags": api.get_tags,
            "status_pages": api.get_status_pages,
            "maintenances": api.get_maintenances,
            "docker_hosts": api.get_docker_hosts,
            "api_keys": api.get_api_keys,
            "settings": api.get_settings,
        }

        print()
        for name, fetch in sections.items():
            try:
                data = fetch()
                snapshot[name] = data
                count = len(data) if isinstance(data, (list, dict)) else 1
                print(f"  {name:<16} {count}")
            except Exception as e:
                errors[name] = f"{type(e).__name__}: {e}"
                snapshot[name] = None
                print(f"  {name:<16} FAILED ({type(e).__name__})")

        # Status page detail lives behind a per-slug call, so fetch each one.
        if snapshot.get("status_pages"):
            details = {}
            for page in snapshot["status_pages"]:
                slug = page.get("slug")
                if not slug:
                    continue
                try:
                    details[slug] = api.get_status_page(slug)
                except Exception as e:
                    errors[f"status_page:{slug}"] = f"{type(e).__name__}: {e}"
            snapshot["status_page_details"] = details
            print(f"  {'status_page_detl':<16} {len(details)}")

    finally:
        api.disconnect()

    if errors:
        snapshot["_meta"]["errors"] = errors

    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(BACKUP_DIR, f"config_snapshot_{stamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, default=str)

    size = os.path.getsize(path)
    print()
    print(f"Wrote {path} ({size:,} bytes)")

    if errors:
        print()
        print(f"WARNING: {len(errors)} section(s) failed to export:")
        for key, msg in errors.items():
            print(f"  {key}: {msg}")
        print("The snapshot is incomplete. Treat it accordingly.")

    print()
    print("This file contains secrets in plain text. It is gitignored; keep it local.")
    print()
    print("For a genuinely restorable backup, snapshot the database on the server:")
    print("  Docker:       docker cp <container>:/app/data/kuma.db ./kuma.db.bak")
    print("                (or back up the mounted volume directory)")
    print("  Bare install: cp /path/to/uptime-kuma/data/kuma.db ./kuma.db.bak")
    print("  Safest is to stop the container first so the file is quiescent.")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
