"""
Regression tests for the incident -> incidents rename in Uptime Kuma 2.1.0.

Uptime Kuma 2.1.0 renamed the singular, nullable ``incident`` object returned by
/api/status-page/{slug} to a plural ``incidents`` array
(louislam/uptime-kuma#6469).

Two distinct bugs are covered:
  1. ``KeyError: 'incident'`` when the server no longer sends the singular key.
  2. Silent data loss: reading only ``incident`` returns None on 2.1.0+ and
     drops the incidents entirely, which is worse than crashing because callers
     get a plausible-looking result with no signal that anything was lost.

No live server required: the websocket call and the HTTP fetch are both mocked.
"""
import unittest
from unittest.mock import MagicMock, patch

from uptime_kuma_api.api import UptimeKumaApi

INCIDENT_V1 = {
    "id": 1,
    "title": "title 1",
    "content": "content 1",
    "style": "danger",
    "pin": 1,
    "createdDate": "2022-12-15 16:51:43",
    "lastUpdatedDate": None,
}


class TestStatusPageIncidents(unittest.TestCase):
    def setUp(self):
        self.api = MagicMock(spec=UptimeKumaApi)
        self.api.url = "http://127.0.0.1:3001"
        self.api.timeout = 10
        self.api.ssl_verify = True
        self.api._call = MagicMock(return_value={"config": {"id": 1, "slug": "slug1"}})
        self.get_status_page = UptimeKumaApi.get_status_page.__get__(self.api)

    def _run(self, http_payload: dict) -> dict:
        response = MagicMock()
        response.json.return_value = http_payload
        with patch("uptime_kuma_api.api.requests.get", return_value=response):
            return self.get_status_page("slug1")

    # --- v2.1.0+ shape: plural array ---

    def test_v2_incidents_array_is_surfaced(self):
        """The full incidents list must reach the caller, not be dropped."""
        page = self._run({
            "config": {"title": "status page 1"},
            "incidents": [INCIDENT_V1],
            "publicGroupList": [],
            "maintenanceList": [],
        })
        self.assertIn("incidents", page)
        self.assertEqual(len(page["incidents"]), 1)
        self.assertEqual(page["incidents"][0]["title"], "title 1")

    def test_v2_incident_singular_backfilled_from_array(self):
        """`incident` stays populated so pre-2.1.0 callers keep working."""
        page = self._run({
            "config": {},
            "incidents": [INCIDENT_V1],
            "publicGroupList": [],
            "maintenanceList": [],
        })
        self.assertIsNotNone(page["incident"])
        self.assertEqual(page["incident"]["title"], "title 1")

    def test_v2_multiple_incidents_all_returned(self):
        second = dict(INCIDENT_V1, id=2, title="title 2")
        page = self._run({
            "config": {},
            "incidents": [INCIDENT_V1, second],
            "publicGroupList": [],
            "maintenanceList": [],
        })
        self.assertEqual(len(page["incidents"]), 2)
        # singular key exposes the first entry
        self.assertEqual(page["incident"]["id"], 1)

    def test_v2_empty_incidents_array(self):
        page = self._run({
            "config": {},
            "incidents": [],
            "publicGroupList": [],
            "maintenanceList": [],
        })
        self.assertEqual(page["incidents"], [])
        self.assertIsNone(page["incident"])

    def test_v2_null_incidents_treated_as_empty(self):
        page = self._run({
            "config": {},
            "incidents": None,
            "publicGroupList": [],
            "maintenanceList": [],
        })
        self.assertEqual(page["incidents"], [])
        self.assertIsNone(page["incident"])

    # --- pre-2.1.0 shape: singular nullable object ---

    def test_v1_singular_incident_normalised_to_array(self):
        page = self._run({
            "config": {},
            "incident": INCIDENT_V1,
            "publicGroupList": [],
            "maintenanceList": [],
        })
        self.assertEqual(len(page["incidents"]), 1)
        self.assertEqual(page["incident"]["title"], "title 1")

    def test_v1_null_incident(self):
        page = self._run({
            "config": {},
            "incident": None,
            "publicGroupList": [],
            "maintenanceList": [],
        })
        self.assertEqual(page["incidents"], [])
        self.assertIsNone(page["incident"])

    # --- neither key present (must not raise) ---

    def test_neither_key_present_does_not_raise(self):
        """This is the original KeyError crash. Absence must be tolerated."""
        page = self._run({
            "config": {},
            "publicGroupList": [],
            "maintenanceList": [],
        })
        self.assertIsNone(page["incident"])
        self.assertEqual(page["incidents"], [])

    # --- style parsing must still apply to every incident ---

    def test_incident_style_parsed_for_all_incidents(self):
        from uptime_kuma_api import IncidentStyle

        second = dict(INCIDENT_V1, id=2, style="info")
        page = self._run({
            "config": {},
            "incidents": [INCIDENT_V1, second],
            "publicGroupList": [],
            "maintenanceList": [],
        })
        self.assertEqual(page["incidents"][0]["style"], IncidentStyle.DANGER)
        self.assertEqual(page["incidents"][1]["style"], IncidentStyle.INFO)
        # the singular key aliases the same object, so it is parsed too
        self.assertEqual(page["incident"]["style"], IncidentStyle.DANGER)

    # --- both keys are always present, whatever the server sent ---

    def test_both_keys_always_present(self):
        for payload in (
            {"config": {}, "incidents": [INCIDENT_V1]},
            {"config": {}, "incident": INCIDENT_V1},
            {"config": {}},
        ):
            payload.setdefault("publicGroupList", [])
            payload.setdefault("maintenanceList", [])
            page = self._run(payload)
            self.assertIn("incident", page, f"missing 'incident' for {payload.keys()}")
            self.assertIn("incidents", page, f"missing 'incidents' for {payload.keys()}")


if __name__ == "__main__":
    unittest.main()
