"""Derives the `integration` marker from the test's base class.

Why derive it instead of listing files
--------------------------------------
The set of tests that need a live Uptime Kuma server is exactly the set that
extends ``UptimeKumaTestCase`` -- that base class's ``setUp`` connects to
127.0.0.1:3001 and deletes every monitor, notification, proxy, tag, status page,
docker host, maintenance and API key on it. So "needs a server" is a property of
the code, not a fact that has to be restated in a list.

Restating it in a list is what this project kept doing, and paying for: the
nine-file unit-test list appeared in `test.yml`, `publish.yml`, `README.md`,
`CONTRIBUTING.md`, `AGENTS.md` and two steering files, with a comment in one of
them instructing that the copies be kept identical. A comment is not a
mechanism, and a seven-place edit gets forgotten. Deriving the marker means
adding a test file requires no CI change at all: a new unit test runs because it
does not extend the base class, and a new integration test is excluded because
it does.

The failure mode is deliberately the safe one. Forgetting to mark an integration
test would previously have meant CI trying to reach a server it does not have --
loud. Under this hook there is nothing to forget. And the inverse (a unit test
silently dropped from CI) cannot happen either, since exclusion requires
inheriting a base class whose whole purpose is the server connection.

Verified equivalent when introduced: the derived set was byte-identical to the
hand-maintained nine-file list, and `pytest` collected the same 226 tests and
1185 subtests as the explicit invocation it replaced.
"""

from uptime_kuma_test_case import UptimeKumaTestCase


def pytest_collection_modifyitems(items):
    """Marks every test in a UptimeKumaTestCase subclass as ``integration``."""
    for item in items:
        cls = getattr(item, "cls", None)
        if cls is not None and issubclass(cls, UptimeKumaTestCase):
            item.add_marker("integration")
