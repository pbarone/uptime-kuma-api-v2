"""Bug A (#91) — string/int id mismatch in all seven ``delete_*`` guards.

Bug condition::

    isBugCondition_A(site, id_) ==
        entityExists(site, int(id_)) AND (id_ NOT IN storedIds(site))

Every ``delete_*`` method guards with
``if id_ not in [i["id"] for i in self.get_X()]`` where the stored ids are
integers. A numeric *string* id therefore never matches (``"371" != 371``), so
the guard raises ``"... does not exist"`` for an entity that demonstrably
exists and the delete is never sent to the server.

These tests are unit tests: no live server. The entity accessor
(``get_monitors`` / ``get_notifications`` / ...) and ``_call`` are mocked, and
the unbound ``delete_*`` function is bound to the mock instance, so only the
guard logic under test executes.

**Validates: Requirements 1.1, 1.2, 2.1, 2.2, 2.3, 3.1, 3.2**
"""

import random
import unittest
from unittest.mock import MagicMock

from uptime_kuma_api import UptimeKumaApi, UptimeKumaException


# (delete method, entity accessor, socket.io event emitted on delete)
DELETE_SITES = [
    ("delete_monitor", "get_monitors", "deleteMonitor"),
    ("delete_notification", "get_notifications", "deleteNotification"),
    ("delete_proxy", "get_proxies", "deleteProxy"),
    ("delete_tag", "get_tags", "deleteTag"),
    ("delete_docker_host", "get_docker_hosts", "deleteDockerHost"),
    ("delete_maintenance", "get_maintenances", "deleteMaintenance"),
    ("delete_api_key", "get_api_keys", "deleteAPIKey"),
]

EXISTING_ID = 371
SERVER_RESPONSE = {"msg": "Deleted Successfully."}


def make_api(accessor, stored_ids):
    """Build a mocked API whose ``accessor`` reports ``stored_ids`` as existing."""
    api = MagicMock(spec=UptimeKumaApi)
    getattr(api, accessor).return_value = [{"id": i} for i in stored_ids]
    api._call.return_value = SERVER_RESPONSE
    return api


def bind(api, method):
    """Bind the real (unmocked) ``delete_*`` implementation to the mock instance."""
    return getattr(UptimeKumaApi, method).__get__(api)


class TestDeleteIdCoercionBugCondition(unittest.TestCase):
    """Property 1 (Bug Condition): a numeric-string id for an existing entity
    must resolve to that entity, send the delete, and not raise.

    **Validates: Requirements 1.1, 1.2, 2.1, 2.2**
    """

    def test_string_id_deletes_existing_entity_at_every_site(self):
        """delete_*("371") with entity 371 present → delete sent, no exception.

        Parametrized over all seven delete sites (scoped property: for every
        site in DELETE_SITES, the caller-supplied id type must not change the
        outcome).
        """
        for method, accessor, event in DELETE_SITES:
            with self.subTest(site=method):
                api = make_api(accessor, [EXISTING_ID])
                delete = bind(api, method)

                try:
                    result = delete(str(EXISTING_ID))
                except UptimeKumaException as e:
                    self.fail(
                        f'{method}("{EXISTING_ID}") raised UptimeKumaException("{e}") '
                        f"although entity {EXISTING_ID} exists"
                    )

                api._call.assert_called_once_with(event, EXISTING_ID)
                self.assertEqual(result, SERVER_RESPONSE)

    def test_string_id_resolves_identically_to_int_id_at_every_site(self):
        """The str and int forms of the same existing id produce the same call.

        **Validates: Requirements 2.2**
        """
        for method, accessor, event in DELETE_SITES:
            with self.subTest(site=method):
                api_int = make_api(accessor, [EXISTING_ID])
                bind(api_int, method)(EXISTING_ID)
                int_calls = api_int._call.call_args_list

                api_str = make_api(accessor, [EXISTING_ID])
                try:
                    bind(api_str, method)(str(EXISTING_ID))
                except UptimeKumaException as e:
                    self.fail(
                        f'{method}("{EXISTING_ID}") raised UptimeKumaException("{e}") '
                        f"while {method}({EXISTING_ID}) succeeded"
                    )

                self.assertEqual(api_str._call.call_args_list, int_calls)


ABSENT_ID = 999


def generated_id_cases(seed=20240501, cases=25):
    """Deterministic id generator: (stored_ids, present_id, absent_id) triples.

    Hypothesis is deliberately not used — it is not a project dependency and CI
    installs only pytest. A seeded ``random.Random`` gives the same broad input
    coverage while keeping the run reproducible.
    """
    rnd = random.Random(seed)
    out = []
    for _ in range(cases):
        stored = rnd.sample(range(1, 10_000), rnd.randint(1, 6))
        present = rnd.choice(stored)
        absent = rnd.randint(10_001, 99_999)
        out.append((stored, present, absent))
    return out


class TestDeleteIdCoercionPreservation(unittest.TestCase):
    """Property 2 (Preservation): outside the bug condition, behavior is unchanged.

    Two invariants, both already true on the unfixed code and therefore the
    baseline the fix must not disturb:

    * an int id for an existing entity sends the delete;
    * an absent id — int or numeric string — raises
      ``UptimeKumaException("... does not exist")`` and sends NO delete.

    (For an absent numeric-string id the unfixed code raises for the *wrong*
    reason — the type mismatch, not absence — but the observable outcome is
    identical before and after the fix, so only the outcome is asserted.)

    **Validates: Requirements 2.3, 3.1, 3.2**
    """

    def test_int_id_deletes_existing_entity_at_every_site(self):
        """delete_*(371) with entity 371 present → delete sent, no exception."""
        for method, accessor, event in DELETE_SITES:
            with self.subTest(site=method):
                api = make_api(accessor, [EXISTING_ID])

                result = bind(api, method)(EXISTING_ID)

                api._call.assert_called_once_with(event, EXISTING_ID)
                self.assertEqual(result, SERVER_RESPONSE)

    def test_absent_int_id_raises_and_sends_no_delete_at_every_site(self):
        """delete_*(999) with 999 absent → raises, nothing sent."""
        for method, accessor, event in DELETE_SITES:
            with self.subTest(site=method):
                api = make_api(accessor, [EXISTING_ID])

                with self.assertRaises(UptimeKumaException) as ctx:
                    bind(api, method)(ABSENT_ID)

                self.assertIn("does not exist", str(ctx.exception))
                api._call.assert_not_called()

    def test_absent_string_id_raises_and_sends_no_delete_at_every_site(self):
        """delete_*("999") with 999 absent → raises, nothing sent."""
        for method, accessor, event in DELETE_SITES:
            with self.subTest(site=method):
                api = make_api(accessor, [EXISTING_ID])

                with self.assertRaises(UptimeKumaException) as ctx:
                    bind(api, method)(str(ABSENT_ID))

                self.assertIn("does not exist", str(ctx.exception))
                api._call.assert_not_called()

    def test_generated_ids_preserve_delete_for_present_int_ids(self):
        """Across generated id sets, an int id present in the store deletes.

        Scoped property: for every site and every generated (stored_ids,
        present_id), ``delete_*(present_id)`` sends exactly one delete carrying
        that id.
        """
        for method, accessor, event in DELETE_SITES:
            for stored, present, _absent in generated_id_cases():
                with self.subTest(site=method, stored=stored, id_=present):
                    api = make_api(accessor, stored)

                    result = bind(api, method)(present)

                    api._call.assert_called_once_with(event, present)
                    self.assertEqual(result, SERVER_RESPONSE)

    def test_generated_ids_preserve_raise_for_absent_ids_of_either_type(self):
        """Across generated id sets, an absent id raises for int and str alike.

        Scoped property: for every site and every generated (stored_ids,
        absent_id), both ``delete_*(absent_id)`` and ``delete_*(str(absent_id))``
        raise ``UptimeKumaException`` and send no delete.
        """
        for method, accessor, _event in DELETE_SITES:
            for stored, _present, absent in generated_id_cases():
                for id_ in (absent, str(absent)):
                    with self.subTest(site=method, stored=stored, id_=id_):
                        api = make_api(accessor, stored)

                        with self.assertRaises(UptimeKumaException) as ctx:
                            bind(api, method)(id_)

                        self.assertIn("does not exist", str(ctx.exception))
                        api._call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
