# Scripts

Development-time tools for discovering Uptime Kuma field changes.

## Setup

The scripts parse Uptime Kuma's Vue/JS source to detect new monitor fields,
notification providers, etc. You need a local checkout of the Uptime Kuma source:

```bash
# Clone the v2 branch (or a specific tag like v2.4.0)
git clone --depth 1 --branch 2 https://github.com/louislam/uptime-kuma.git scripts/uptime-kuma

# For comparison against an older version:
git clone --depth 1 --branch 1.23.16 https://github.com/louislam/uptime-kuma.git scripts/uptime-kuma-old
```

These directories are gitignored — they won't be committed.

## Scripts

- `build_inputs.py` — Parses Vue source to discover monitor form fields
- `build_models.py` — Extracts model definitions
- `build_monitor_types.py` — Discovers monitor type identifiers
- `build_notifications.py` — Discovers notification provider fields
- `build_notification_docstring.py` — Generates docstring entries for notification params
