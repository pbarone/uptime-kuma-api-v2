"""Monitor list cache staleness on Uptime Kuma 2.x.

Uptime Kuma 2.x replaced the post-mutation full ``monitorList`` broadcast with
the deltas ``updateMonitorIntoList`` / ``deleteMonitorFromList``, which this
library registers no handler for. The cached monitor list is therefore
session-stale from the first mutation onwards, and the two guards that decide
from that cache -- ``delete_monitor`` and ``delete_monitor_tag`` -- reject ids
the server demonstrably has.

Bug condition::

    isStaleGuardCondition(guard, cache_state, server_state) ==
        guard IN {delete_monitor, delete_monitor_tag}
        AND cache_state <> server_state

These are unit tests: no live server. ``_call`` is mocked with a side effect
that mimics the server contract -- a ``getMonitorList`` call populates the
cached monitor list with the *fresh* server view exactly as
``_event_monitor_list`` would, before the ack returns -- while
``wait_for_event``, ``_get_event_data``, ``get_monitors`` and the guard bodies
themselves run for real.

The file carries three kinds of test. ``TestGuardsDecideOnFreshData`` is the
bug-condition evidence and FAILS on the unfixed code. The preservation baseline
classes after it record behaviour observed on the unfixed code first and then
asserted, so the fix has something concrete to be measured against -- those pass
before and after the fix, which is the point of them. Last come the delta
handler tests, which use a second harness and assert on the cached monitor list
directly; against the unfixed code they fail only with ``AttributeError``
because the handlers do not exist yet, which is weak evidence, so they are
correctness tests for new code rather than proof the defect was real.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3,
2.4, 2.5, 2.6, 2.7, 2.9, 3.1, 3.3, 3.4, 3.5, 3.7, 3.9**
"""

import inspect
import random
import time
import unittest
from copy import deepcopy
from unittest.mock import MagicMock

from uptime_kuma_api import Event, Timeout, UptimeKumaApi, UptimeKumaException


SERVER_RESPONSE = {"msg": "Deleted Successfully."}

# Left as plain MagicMock attributes: the transport, and the single-monitor
# read that delete_monitor_tag does after a successful delete (it only patches
# the cache entry back, and is not part of any guard decision).
STUBBED_ON_MOCK = frozenset({"_call", "get_monitor"})

# Bound for real on every guard harness. get_monitors -> _get_event_data is the
# read the guards decide from, and wait_for_event is the wrap they sit inside.
HARNESS_REAL_METHODS = ("wait_for_event", "_get_event_data", "get_monitors")


def monitor(id_, tags=None, **extra):
    """A monitor entry shaped like the server's ``monitorList`` values."""
    entry = {
        "id": id_,
        "name": "monitor {0}".format(id_),
        "active": 1,
        "type": "http",
        "authMethod": None,
        "notificationIDList": {},
        "tags": list(tags or []),
    }
    entry.update(extra)
    return entry


def tag(tag_id, monitor_id, value=""):
    """A monitor tag entry as it appears in a monitor's ``tags`` list."""
    return {"tag_id": tag_id, "monitor_id": monitor_id, "value": value}


def cache_of(*monitors):
    """The cached monitor list: a dict keyed by *stringified* monitor id."""
    return {str(m["id"]): m for m in monitors}


def sent_events(api):
    """The event names ``_call`` was invoked with, in order."""
    return [call.args[0] if call.args else None for call in api._call.call_args_list]


def _self_methods_called_by(func):
    """Plain ``UptimeKumaApi`` methods that ``func`` calls on ``self``.

    Read out of the function's own bytecode rather than hardcoded. The guards
    must run against real private plumbing, not against plumbing the mock has
    silently stubbed to a MagicMock -- but naming a helper the class does not
    have yet would make this harness raise ``AttributeError`` instead of
    letting the guard fail for the real reason. Discovering the set from the
    guard body gives both: today it resolves to what exists today.
    """
    return tuple(
        name for name in func.__code__.co_names
        if name not in STUBBED_ON_MOCK
        and inspect.isfunction(getattr(UptimeKumaApi, name, None))
    )


def _server_side_effect(api, fresh_cache):
    """A ``_call`` side effect that mimics the 2.x server contract."""

    def _call(event, data=None):
        if event == "getMonitorList":
            # The server emits monitorList and only then acks, and the sync
            # socket.io client dispatches both on the same read-loop thread --
            # so the cache is already replaced by the time the caller resumes.
            api._event_data[Event.MONITOR_LIST] = deepcopy(fresh_cache)
            return {}
        if event in ("deleteMonitor", "deleteMonitorTag"):
            return dict(SERVER_RESPONSE)
        return {}

    return _call


def make_guard_api(guard, stale_cache, fresh_cache):
    """Build the guard harness.

    :param guard: name of the guard under test, e.g. ``"delete_monitor"``.
    :param stale_cache: the cached monitor list the session starts with.
    :param fresh_cache: the monitor list the server would answer
        ``getMonitorList`` with.
    :return: ``(api, bound_guard)``.
    """
    api = MagicMock(spec=UptimeKumaApi)
    api._event_data = {Event.MONITOR_LIST: deepcopy(stale_cache)}
    api.wait_events = 0
    api.timeout = 1
    api._call.side_effect = _server_side_effect(api, fresh_cache)

    guard_func = getattr(UptimeKumaApi, guard)
    for name in dict.fromkeys(HARNESS_REAL_METHODS + _self_methods_called_by(guard_func)):
        setattr(api, name, getattr(UptimeKumaApi, name).__get__(api))

    return api, guard_func.__get__(api)


# The six events _get_event_data short-circuits to [] when the cached monitor
# list is the {} "server has zero monitors" sentinel (api.py, _get_event_data).
MONITOR_SCOPED_EVENTS = (
    Event.AVG_PING,
    Event.UPTIME,
    Event.HEARTBEAT_LIST,
    Event.IMPORTANT_HEARTBEAT_LIST,
    Event.CERT_INFO,
    Event.HEARTBEAT,
)


def initial_event_data():
    """``_event_data`` exactly as ``UptimeKumaApi.__init__`` builds it.

    Deliberately mirrors the real dict, including the fact that
    ``Event.HEARTBEAT`` gets **no** slot there -- a test that needs one has to
    add it, and say why.
    """
    return {
        Event.MONITOR_LIST: None,
        Event.NOTIFICATION_LIST: None,
        Event.PROXY_LIST: None,
        Event.STATUS_PAGE_LIST: None,
        Event.HEARTBEAT_LIST: None,
        Event.IMPORTANT_HEARTBEAT_LIST: None,
        Event.AVG_PING: None,
        Event.UPTIME: None,
        Event.INFO: None,
        Event.CERT_INFO: None,
        Event.DOCKER_HOST_LIST: None,
        Event.AUTO_LOGIN: None,
        Event.MAINTENANCE_LIST: None,
        Event.API_KEY_LIST: None,
    }


def make_api(monitor_cache=None, real=(), timeout=1):
    """Build a mock API for the non-guard preservation tests.

    Same shape as the guard harness -- ``MagicMock(spec=UptimeKumaApi)`` with a
    real ``_event_data`` and named methods bound for real -- but without the
    stale/fresh server contract, because these tests exercise a single method
    rather than a guard decision.

    :param monitor_cache: value for the cached monitor list; ``None`` leaves it
        at the pre-login ``None`` that ``__init__`` sets.
    :param real: names of ``UptimeKumaApi`` methods to bind for real.
    :param timeout: ``api.timeout``, kept small so a wait that should not happen
        fails the test quickly instead of hanging it.
    """
    api = MagicMock(spec=UptimeKumaApi)
    api._event_data = initial_event_data()
    if monitor_cache is not None:
        api._event_data[Event.MONITOR_LIST] = deepcopy(monitor_cache)
    api.wait_events = 0
    api.timeout = timeout
    api._call.return_value = dict(SERVER_RESPONSE)

    for name in real:
        setattr(api, name, getattr(UptimeKumaApi, name).__get__(api))

    return api


# The three cache writers on the socket.io read-loop thread: the v1.x full-list
# broadcast handler and the two 2.x delta handlers. All bound for real on the
# handler harness so a test can deliver any mix of them.
HANDLER_REAL_METHODS = (
    "_event_monitor_list",
    "_event_update_monitor_into_list",
    "_event_delete_monitor_from_list",
)


def make_handler_api(monitor_cache=None, real=(), timeout=1):
    """Build the handler harness.

    A ``MagicMock(spec=UptimeKumaApi)`` with a real ``_event_data`` dict and the
    delta handlers bound for real, so a test can deliver a server payload and
    assert on the cached monitor list **directly** -- no guard, no transport, no
    ``get_monitors()`` parsing in the way.

    :param monitor_cache: value for the cached monitor list. ``None`` leaves it
        at the pre-login ``None``; ``{}`` is the zero-monitor sentinel.
    :param real: extra ``UptimeKumaApi`` method names to bind for real, e.g.
        ``_get_event_data`` when a test also reads the cache back out.
    :param timeout: ``api.timeout``, kept small so a read that should
        short-circuit fails fast instead of hanging.
    """
    return make_api(
        monitor_cache,
        real=tuple(HANDLER_REAL_METHODS) + tuple(real),
        timeout=timeout,
    )


class TestGuardsDecideOnFreshData(unittest.TestCase):
    """Property 1 (Bug Condition): a cache-reading guard must decide on fresh
    data, so it sends the delete for every entity the server actually has.

    Both tests FAIL against the unfixed code -- the guard raises the production
    ``UptimeKumaException`` and never reaches ``_call`` -- which is the
    requirement 2.9 evidence that the defect is real.

    **Validates: Requirements 1.2, 1.6, 2.2, 2.6, 2.9**
    """

    def test_delete_monitor_sends_delete_for_id_present_only_after_refresh(self):
        """Test 14 -- monitor 7 is absent from the stale cache, present on the
        server. ``delete_monitor(7)`` must send ``deleteMonitor``.

        **Validates: Requirements 1.2, 2.2**
        """
        stale = cache_of(monitor(1), monitor(2))
        fresh = cache_of(monitor(1), monitor(2), monitor(7))
        api, delete_monitor = make_guard_api("delete_monitor", stale, fresh)

        try:
            result = delete_monitor(7)
        except UptimeKumaException as e:
            self.fail(
                "delete_monitor(7) raised {0}(\"{1}\") although the server has "
                "monitor 7; _call events sent: {2}".format(
                    type(e).__name__, e, sent_events(api)
                )
            )

        api._call.assert_any_call("deleteMonitor", 7)
        self.assertEqual(result, SERVER_RESPONSE)

    def test_delete_monitor_tag_sends_delete_for_tag_present_only_after_refresh(self):
        """Test 15 -- the stale cache entry for monitor 1 carries no matching
        ``(tag_id, monitor_id, value)`` triple, the server's does.
        ``delete_monitor_tag`` must send ``deleteMonitorTag``.

        **Validates: Requirements 1.6, 2.6**
        """
        stale = cache_of(monitor(1, tags=[tag(9, 1, "other")]))
        fresh = cache_of(monitor(1, tags=[tag(9, 1, "other"), tag(3, 1, "prod")]))
        api, delete_monitor_tag = make_guard_api("delete_monitor_tag", stale, fresh)

        try:
            result = delete_monitor_tag(tag_id=3, monitor_id=1, value="prod")
        except UptimeKumaException as e:
            self.fail(
                "delete_monitor_tag(tag_id=3, monitor_id=1, value=\"prod\") raised "
                "{0}(\"{1}\") although the server has that tag; _call events "
                "sent: {2}".format(type(e).__name__, e, sent_events(api))
            )

        api._call.assert_any_call("deleteMonitorTag", (3, 1, "prod"))
        self.assertEqual(result, SERVER_RESPONSE)


class TestGuardsStillRejectWhatDoesNotExist(unittest.TestCase):
    """Property 2 (Preservation): the refresh makes a guard's input
    authoritative, it does not weaken the guard.

    The stale and fresh views are the *same* here -- these are not
    bug-condition inputs, so the guard must reach the same verdict before and
    after the fix. Each asserts on the exact production message and on the
    delete never reaching the transport.

    ``deleteMonitor`` / ``deleteMonitorTag`` absence from the sent events is
    asserted rather than ``_call.assert_not_called()``: the fix legitimately
    adds one ``getMonitorList`` refresh, and this baseline must survive that.

    **Validates: Requirements 3.3, 3.4**
    """

    def test_delete_monitor_with_genuinely_absent_id_raises_and_sends_no_delete(self):
        """Test 16 -- monitor 7 exists nowhere, not in the cache and not on the
        server. The guard must still reject it.

        **Validates: Requirements 3.3**
        """
        present = cache_of(monitor(1), monitor(2))
        api, delete_monitor = make_guard_api("delete_monitor", present, present)

        with self.assertRaises(UptimeKumaException) as ctx:
            delete_monitor(7)

        self.assertEqual(str(ctx.exception), "monitor does not exist")
        self.assertNotIn("deleteMonitor", sent_events(api))

    def test_numeric_string_id_still_deletes_existing_monitor(self):
        """Test 17a -- ``delete_monitor("7")`` with monitor 7 present still
        coerces and sends the delete, per the shipped #91 contract.

        **Validates: Requirements 3.4**
        """
        present = cache_of(monitor(1), monitor(7))
        api, delete_monitor = make_guard_api("delete_monitor", present, present)

        result = delete_monitor("7")

        api._call.assert_any_call("deleteMonitor", 7)
        self.assertEqual(result, SERVER_RESPONSE)

    def test_non_numeric_string_id_raises_library_exception_not_value_error(self):
        """Test 17b -- ``delete_monitor("not-an-id")`` still raises the
        library's own exception. A leaked ``ValueError`` from the ``int()``
        coercion would break the single-hierarchy contract callers catch on.

        **Validates: Requirements 3.4**
        """
        present = cache_of(monitor(1), monitor(7))
        api, delete_monitor = make_guard_api("delete_monitor", present, present)

        with self.assertRaises(UptimeKumaException) as ctx:
            delete_monitor("not-an-id")

        self.assertEqual(str(ctx.exception), "monitor does not exist")
        self.assertNotIsInstance(ctx.exception, (ValueError, Timeout))
        self.assertNotIn("deleteMonitor", sent_events(api))

    def test_delete_monitor_tag_with_absent_tag_raises_and_sends_nothing(self):
        """Test 18 -- the tag analogue: a triple neither the cache nor the
        server has is still rejected.

        **Validates: Requirements 3.3**
        """
        present = cache_of(monitor(1, tags=[tag(9, 1, "other")]))
        api, delete_monitor_tag = make_guard_api("delete_monitor_tag", present, present)

        with self.assertRaises(UptimeKumaException) as ctx:
            delete_monitor_tag(tag_id=3, monitor_id=1, value="prod")

        self.assertEqual(str(ctx.exception), "monitor tag does not exist")
        self.assertNotIn("deleteMonitorTag", sent_events(api))


class _RecordingProperty:
    """A stand-in for a property that counts how often it is read.

    ``api.version`` is a property on ``UptimeKumaApi``, so on a
    ``MagicMock(spec=...)`` it is just a child mock and a plain read of it leaves
    no trace at all. Installing this on the mock's own per-instance type -- which
    ``mock`` creates fresh for every mock, so nothing leaks between tests -- makes
    the read observable. ``__set__`` is defined so it is a *data* descriptor and
    therefore cannot be shadowed by anything the mock puts on the instance.
    """

    def __init__(self, value):
        self.value = value
        self.reads = 0

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        self.reads += 1
        return self.value

    def __set__(self, instance, value):
        self.value = value


class TestRefreshMonitorListCost(unittest.TestCase):
    """Property 2 (Preservation): the refresh helper costs exactly one RPC and
    never consults the server version.

    Test 19. Requirement 3.2 does not merely permit the refresh to be
    ungated -- it argues that gating it would be *more* expensive than the RPC
    it guards, because ``self.version`` is a property that routes through
    ``info()`` -> ``_get_event_data`` and pays a 0.2 s ``wait_events`` sleep to
    save a 2-6 ms round trip. That argument only holds while the helper stays a
    single ``getMonitorList`` with no version lookup anywhere in it, on v1.x
    sessions as much as on 2.x ones. This is the test that keeps it true.

    Both halves are checked two ways, because neither way alone is sufficient:

    * **Statically**, from the helper's own bytecode -- the ``co_names`` idiom
      ``_self_methods_called_by`` already uses. A version read added inside a
      branch this test does not happen to execute would still be named there,
      so the static half sees code the runtime half cannot reach.
    * **At runtime**, by making a read of ``version`` recordable and asserting
      the ``info`` / ``_parsed_version`` mocks were never called. That half sees
      an *indirect* lookup the static half cannot: a name reached through a
      helper rather than spelled out in this function. It is decisive here
      because every other method on the harness is a stub, so the only real
      code running is the helper itself.

    **Validates: Requirements 2.10, 3.2**
    """

    # The three ways api.py can learn the server version. self.version is the
    # property; _parsed_version() and info() are the two routes into it.
    VERSION_ACCESSORS = ("version", "_parsed_version", "info")

    @staticmethod
    def _make_api():
        """The refresh harness: only ``_refresh_monitor_list`` runs for real.

        ``version`` is replaced on the mock's own (per-instance) type by a
        descriptor that counts reads, since a plain attribute read leaves no
        trace on a ``MagicMock``. It answers with a real-looking version string
        so that a lookup which *did* sneak in would proceed normally and be
        caught by the assertion rather than derailed by a mock value.
        """
        api = make_api(cache_of(monitor(1)), real=("_refresh_monitor_list",))
        type(api).version = _RecordingProperty("2.4.0")
        return api

    def test_issues_exactly_one_get_monitor_list_call(self):
        """One RPC, ``getMonitorList``, no payload -- and nothing else.

        The single-call shape is also what keeps the seven
        ``_call.assert_called_once_with("deleteMonitor", 371)`` assertions in
        ``tests/test_delete_id_coercion_v2.py`` passing unmodified: the helper is
        stubbed out there, so the guards' visible transport is unchanged.

        **Validates: Requirements 2.10**
        """
        api = self._make_api()

        result = api._refresh_monitor_list()

        api._call.assert_called_once_with("getMonitorList")
        # The refresh's product is the cache write _event_monitor_list does, not
        # a return value -- callers read the cache afterwards.
        self.assertIsNone(result)

    def test_touches_no_version_accessor_at_runtime(self):
        """Calling the helper reads no version, directly or indirectly.

        **Validates: Requirements 3.2**
        """
        api = self._make_api()

        api._refresh_monitor_list()

        self.assertEqual(
            type(api).version.reads,
            0,
            "_refresh_monitor_list read self.version; requirement 3.2 forbids a "
            "version lookup on this path because it costs a 0.2s wait_events "
            "sleep to save a 2-6ms RPC",
        )
        api.info.assert_not_called()
        api._parsed_version.assert_not_called()

    def test_names_no_version_accessor_in_its_bytecode(self):
        """No version accessor is even *named* in the helper.

        **Validates: Requirements 3.2**
        """
        names = UptimeKumaApi._refresh_monitor_list.__code__.co_names

        self.assertIn("_call", names)
        for accessor in self.VERSION_ACCESSORS:
            with self.subTest(accessor=accessor):
                self.assertNotIn(accessor, names)


class TestWaitForEventFirstEventOnlySemantics(unittest.TestCase):
    """Property 2 (Preservation): ``wait_for_event``'s observable semantics.

    Test 20. The helper loops only *while* the cached entry is ``None`` and
    never resets it, so once login has populated the entry the four monitor
    wraps return immediately -- it cannot be the mechanism that refreshes
    anything. That is the no-op the fix documents in place rather than changes,
    and these tests pin the behaviour so "documented, not changed" is checkable.

    **Validates: Requirements 1.7, 2.7**
    """

    def test_populated_entry_returns_without_waiting(self):
        """A populated entry: the wrap returns at once and leaves it alone.

        ``timeout`` is 0.5 s, so a wrap that waited at all would raise
        ``Timeout`` instead of returning.

        **Validates: Requirements 1.7, 2.7**
        """
        cache = cache_of(monitor(1))
        api = make_api(cache, real=("wait_for_event",), timeout=0.5)
        before = api._event_data[Event.MONITOR_LIST]

        started = time.monotonic()
        with api.wait_for_event(Event.MONITOR_LIST):
            pass
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 0.1)
        self.assertIs(api._event_data[Event.MONITOR_LIST], before)
        self.assertEqual(api._event_data[Event.MONITOR_LIST], cache)

    def test_none_entry_still_waits_and_times_out(self):
        """The contrast that makes the no-op concrete: ``None`` is the only
        state the wrap actually waits in, so on a session's first mutation it
        still blocks -- which is why the wraps are not dead code.

        **Validates: Requirements 1.7**
        """
        api = make_api(None, real=("wait_for_event",), timeout=0.05)

        with self.assertRaises(Timeout):
            with api.wait_for_event(Event.MONITOR_LIST):
                pass


class TestZeroMonitorSentinel(unittest.TestCase):
    """Property 2 (Preservation): the ``{}`` zero-monitor sentinel.

    An empty cached monitor list means "the server has no monitors", and
    ``_get_event_data`` short-circuits the six monitor-scoped events to ``[]``
    instead of blocking until the timeout. No part of the fix may clear the
    cache in a way that collides with this.

    **Validates: Requirements 3.5**
    """

    def test_empty_monitor_list_short_circuits_all_monitor_scoped_events(self):
        """``{}`` cache: each of the six returns ``[]`` immediately.

        ``timeout`` is 0.5 s, so a miss on the short-circuit raises ``Timeout``.

        **Validates: Requirements 3.5**
        """
        for event in MONITOR_SCOPED_EVENTS:
            with self.subTest(event=event):
                api = make_api({}, real=("_get_event_data",), timeout=0.5)
                # __init__ gives Event.HEARTBEAT no _event_data slot, but
                # _get_event_data's short-circuit list names it, so seed the
                # slot to make that branch reachable for all six.
                api._event_data.setdefault(Event.HEARTBEAT, None)

                self.assertEqual(api._get_event_data(event), [])
                self.assertEqual(api._event_data[Event.MONITOR_LIST], {})

    def test_empty_monitor_list_reads_back_as_no_monitors(self):
        """``get_monitors()`` on the sentinel returns ``[]``, not a ``Timeout``.

        **Validates: Requirements 3.5**
        """
        api = make_api({}, real=("_get_event_data", "get_monitors"), timeout=0.5)

        self.assertEqual(api.get_monitors(), [])
        self.assertEqual(api._event_data[Event.MONITOR_LIST], {})


class TestMonitorTagCachePatching(unittest.TestCase):
    """Property 2 (Preservation): both monitor-tag methods keep patching the
    target monitor into the cache under its **string** key.

    The cached monitor list arrives from the server as a JSON object, so its
    keys are strings; an int key here would be invisible to every later read.

    **Validates: Requirements 3.7**
    """

    def test_add_monitor_tag_writes_target_monitor_under_string_key(self):
        """**Validates: Requirements 3.7**"""
        api = make_api(cache_of(monitor(1)), real=("add_monitor_tag",))
        patched = monitor(4, tags=[tag(3, 4, "prod")])
        api.get_monitor.return_value = patched

        api.add_monitor_tag(tag_id=3, monitor_id=4, value="prod")

        cache = api._event_data[Event.MONITOR_LIST]
        self.assertIn("4", cache)
        self.assertNotIn(4, cache)
        self.assertIs(cache["4"], patched)

    def test_add_monitor_tag_on_a_none_cache_creates_a_string_keyed_dict(self):
        """A pre-login ``None`` cache is initialised rather than raising.

        **Validates: Requirements 3.7**
        """
        api = make_api(None, real=("add_monitor_tag",))
        patched = monitor(4, tags=[tag(3, 4, "prod")])
        api.get_monitor.return_value = patched

        api.add_monitor_tag(tag_id=3, monitor_id=4, value="prod")

        self.assertEqual(api._event_data[Event.MONITOR_LIST], {"4": patched})

    def test_delete_monitor_tag_writes_target_monitor_under_string_key(self):
        """**Validates: Requirements 3.7**"""
        present = cache_of(monitor(1, tags=[tag(3, 1, "prod")]))
        api, delete_monitor_tag = make_guard_api("delete_monitor_tag", present, present)
        patched = monitor(1, tags=[])
        api.get_monitor.return_value = patched

        delete_monitor_tag(tag_id=3, monitor_id=1, value="prod")

        cache = api._event_data[Event.MONITOR_LIST]
        self.assertIn("1", cache)
        self.assertNotIn(1, cache)
        self.assertIs(cache["1"], patched)


class TestV1FullListBroadcastStillDrivesTheCache(unittest.TestCase):
    """Property 2 (Preservation): v1.x inertness.

    v1.x re-broadcasts the whole ``monitorList`` after every mutation and never
    emits a delta, so ``_event_monitor_list`` remains the only thing that writes
    the cache on a v1.x session. It stores the payload as-is, and this asserts
    that identity -- a delta handler contributing anything on this path, or the
    full-list handler starting to transform the payload, would break it.

    **Validates: Requirements 3.1**
    """

    def test_full_list_broadcast_populates_the_cache_unchanged(self):
        """Login broadcast, then the post-mutation re-broadcast v1.x sends.

        **Validates: Requirements 3.1**
        """
        api = make_api(
            None,
            real=("_event_monitor_list", "_get_event_data", "get_monitors"),
        )

        at_login = cache_of(monitor(1), monitor(2))
        api._event_monitor_list(at_login)
        self.assertIs(api._event_data[Event.MONITOR_LIST], at_login)

        # v1.x answers a mutation with the whole list again, not a delta
        after_add = cache_of(monitor(1), monitor(2), monitor(7))
        api._event_monitor_list(after_add)
        self.assertIs(api._event_data[Event.MONITOR_LIST], after_add)

        self.assertEqual([m["id"] for m in api.get_monitors()], [1, 2, 7])
        api._call.assert_not_called()


class TestUpdateMonitorIntoListHandler(unittest.TestCase):
    """Property 3 (Bug Condition): ``updateMonitorIntoList`` keeps the cached
    monitor list coherent.

    2.x sends this delta instead of a full ``monitorList`` after add, edit,
    pause, resume and the monitor tag operations. The payload is
    ``{id: monitor}`` with one or more entries, and every entry must land in the
    cache under its **stringified** id, storing the raw server payload unparsed
    -- ``get_monitors()`` / ``get_monitor()`` do the parsing on the way out.

    Tests 1-6. These are correctness tests for new code: against the unfixed
    code they fail with ``AttributeError`` because the handler does not exist,
    which the design calls weak evidence. The requirement 2.9 proof is
    ``TestGuardsDecideOnFreshData``.

    **Validates: Requirements 1.1, 1.4, 1.5, 2.1, 2.4, 2.5, 3.7**
    """

    def test_merges_a_new_id_into_a_populated_cache(self):
        """Test 1 -- an added monitor becomes visible without disturbing the
        entries already cached.

        **Validates: Requirements 1.1, 2.1**
        """
        api = make_handler_api(cache_of(monitor(1), monitor(2)))
        added = monitor(7)

        api._event_update_monitor_into_list({"7": added})

        cache = api._event_data[Event.MONITOR_LIST]
        self.assertEqual(sorted(cache), ["1", "2", "7"])
        # stored raw: the handler must not parse, deepcopy or reshape the entry
        self.assertIs(cache["7"], added)

    def test_merges_a_multi_entry_payload(self):
        """Test 2 -- the payload may carry more than one ``{id: monitor}``
        entry, and every one of them must be merged.

        **Validates: Requirements 2.1**
        """
        api = make_handler_api(cache_of(monitor(1)))
        seven, eight = monitor(7), monitor(8)

        api._event_update_monitor_into_list({"7": seven, "8": eight})

        cache = api._event_data[Event.MONITOR_LIST]
        self.assertEqual(sorted(cache), ["1", "7", "8"])
        self.assertIs(cache["7"], seven)
        self.assertIs(cache["8"], eight)

    def test_replaces_an_existing_entry_with_post_edit_values(self):
        """Test 3 -- after ``edit_monitor`` the delta carries the whole updated
        monitor, so the cached entry is replaced rather than merged field-wise.

        **Validates: Requirements 1.4, 2.4**
        """
        api = make_handler_api(cache_of(monitor(1, interval=60, name="before")))

        api._event_update_monitor_into_list(
            {"1": monitor(1, interval=20, name="after")}
        )

        cache = api._event_data[Event.MONITOR_LIST]
        self.assertEqual(sorted(cache), ["1"])
        self.assertEqual(cache["1"]["interval"], 20)
        self.assertEqual(cache["1"]["name"], "after")

    def test_reflects_a_changed_active_flag(self):
        """Test 4 -- pause / resume answer with this delta, so the cache must
        pick up the new ``active`` value. ``pause_monitor`` /
        ``resume_monitor`` are deliberately left unmodified by the fix and rely
        entirely on this handler.

        **Validates: Requirements 1.5, 2.5**
        """
        api = make_handler_api(cache_of(monitor(1, active=1)))

        api._event_update_monitor_into_list({"1": monitor(1, active=0)})
        self.assertEqual(api._event_data[Event.MONITOR_LIST]["1"]["active"], 0)

        api._event_update_monitor_into_list({"1": monitor(1, active=1)})
        self.assertEqual(api._event_data[Event.MONITOR_LIST]["1"]["active"], 1)

    def test_initialises_a_none_cache_without_raising(self):
        """Test 5 -- a delta arriving before any full list initialises the
        cache, mirroring the ``add_monitor_tag`` precedent. Populating is safe
        here (unlike in the delete handler) because the result is never empty,
        so it cannot counterfeit the zero-monitor sentinel.

        **Validates: Requirements 2.1, 3.7**
        """
        api = make_handler_api(None)
        self.assertIsNone(api._event_data[Event.MONITOR_LIST])
        added = monitor(7)

        api._event_update_monitor_into_list({"7": added})

        self.assertEqual(api._event_data[Event.MONITOR_LIST], {"7": added})

    def test_coerces_int_payload_keys_to_str(self):
        """Test 6 -- the cache is string-keyed, so an int key would be
        invisible to every later read. JSON object keys arrive as strings
        today; the coercion makes the handler indifferent to a server that ever
        sends them as ints.

        **Validates: Requirements 2.1**
        """
        api = make_handler_api(cache_of(monitor(1)))
        added = monitor(7)

        api._event_update_monitor_into_list({7: added})

        cache = api._event_data[Event.MONITOR_LIST]
        self.assertIn("7", cache)
        self.assertNotIn(7, cache)
        self.assertIs(cache["7"], added)


class TestDeleteMonitorFromListHandler(unittest.TestCase):
    """Property 3 (Bug Condition): ``deleteMonitorFromList`` removes the
    monitor from the cached list.

    2.x sends this delta instead of a full ``monitorList`` after a delete,
    carrying the id **alone** -- and as the raw ``monitor.id``, so it arrives as
    an ``int`` while the cache is string-keyed. One event per monitor, so a
    group delete cascading to children arrives as several of these.

    Tests 7-11.

    **Validates: Requirements 1.3, 2.3, 3.5**
    """

    def test_removes_an_entry_given_an_int_id(self):
        """Test 7 -- the load-bearing case: the server sends the id as an int
        and the cache key is a string, so without coercion nothing is removed.

        **Validates: Requirements 1.3, 2.3**
        """
        api = make_handler_api(cache_of(monitor(1), monitor(2), monitor(7)))

        api._event_delete_monitor_from_list(7)

        self.assertEqual(sorted(api._event_data[Event.MONITOR_LIST]), ["1", "2"])

    def test_removes_an_entry_given_a_string_id(self):
        """Test 8 -- an already-stringified id is handled identically, so the
        coercion is a no-op rather than a second code path.

        **Validates: Requirements 2.3**
        """
        api = make_handler_api(cache_of(monitor(1), monitor(2), monitor(7)))

        api._event_delete_monitor_from_list("7")

        self.assertEqual(sorted(api._event_data[Event.MONITOR_LIST]), ["1", "2"])

    def test_absent_id_is_a_no_op(self):
        """Test 9 -- a delta for a monitor the cache never had leaves the cache
        contents alone rather than raising. A group cascade can legitimately
        deliver an id already gone.

        **Validates: Requirements 2.3**
        """
        api = make_handler_api(cache_of(monitor(1), monitor(2)))
        before = deepcopy(api._event_data[Event.MONITOR_LIST])

        api._event_delete_monitor_from_list(7)

        self.assertEqual(api._event_data[Event.MONITOR_LIST], before)

    def test_none_cache_stays_none_and_never_becomes_empty(self):
        """Test 10 -- a delete delta arriving before any full list must return
        early. Creating ``{}`` here would fabricate the "server has zero
        monitors" sentinel and short-circuit the six monitor-scoped events to
        ``[]`` while monitors may well exist.

        **Validates: Requirements 3.5**
        """
        api = make_handler_api(None)

        api._event_delete_monitor_from_list(7)

        self.assertIsNone(
            api._event_data[Event.MONITOR_LIST],
            "a delete delta on a None cache must not fabricate the {} "
            "zero-monitor sentinel",
        )

    def test_removing_the_last_monitor_leaves_the_sentinel_working(self):
        """Test 11 -- ``{}`` produced by deleting the last monitor is benign: it
        then means exactly what the sentinel says it means, so
        ``_get_event_data`` short-circuiting the six monitor-scoped events to
        ``[]`` is correct rather than a collision.

        ``timeout`` is 0.5 s, so a miss on the short-circuit raises ``Timeout``.

        **Validates: Requirements 3.5**
        """
        api = make_handler_api(
            cache_of(monitor(7)), real=("_get_event_data",), timeout=0.5
        )
        # __init__ gives Event.HEARTBEAT no _event_data slot, but
        # _get_event_data's short-circuit list names it, so seed the slot to
        # make that branch reachable for all six.
        api._event_data.setdefault(Event.HEARTBEAT, None)

        api._event_delete_monitor_from_list(7)

        self.assertEqual(api._event_data[Event.MONITOR_LIST], {})
        for event in MONITOR_SCOPED_EVENTS:
            with self.subTest(event=event):
                self.assertEqual(api._get_event_data(event), [])


class TestDeltaHandlersRebindRatherThanMutate(unittest.TestCase):
    """Property 3 / Preservation: both handlers build a new dict and rebind it.

    Test 12. These are the first cache writers that run on the socket.io
    read-loop thread, while ``_get_event_data`` copies the same dict on the
    caller's thread. Rebinding a fully-built dict means a reader holding the old
    one sees a consistent snapshot instead of a dict mid-mutation.

    **Validates: Requirements 3.5, 3.9**
    """

    def test_update_handler_leaves_the_previous_dict_untouched(self):
        """**Validates: Requirements 3.5, 3.9**"""
        api = make_handler_api(cache_of(monitor(1)))
        held_by_reader = api._event_data[Event.MONITOR_LIST]
        snapshot = deepcopy(held_by_reader)

        api._event_update_monitor_into_list({"7": monitor(7)})

        after = api._event_data[Event.MONITOR_LIST]
        self.assertIsNot(after, held_by_reader)
        self.assertEqual(held_by_reader, snapshot)
        self.assertIn("7", after)

    def test_delete_handler_leaves_the_previous_dict_untouched(self):
        """**Validates: Requirements 3.5, 3.9**"""
        api = make_handler_api(cache_of(monitor(1), monitor(7)))
        held_by_reader = api._event_data[Event.MONITOR_LIST]
        snapshot = deepcopy(held_by_reader)

        api._event_delete_monitor_from_list(7)

        after = api._event_data[Event.MONITOR_LIST]
        self.assertIsNot(after, held_by_reader)
        self.assertEqual(held_by_reader, snapshot)
        self.assertNotIn("7", after)


def generated_delta_cases(seed=20260801, cases=25):
    """Deterministic delta generator: cache states x payload shapes.

    Yields ``(start_ids, replace_ids, new_ids, key_type, batched)`` tuples.

    * ``start_ids`` -- the monitors already cached. Sized to cover the three
      states that matter: empty (the ``{}`` sentinel), a single monitor, and
      many.
    * ``replace_ids`` -- a subset of ``start_ids`` the payload re-sends, i.e.
      the edit / pause / resume shape where an entry is replaced.
    * ``new_ids`` -- ids the cache does not have, drawn from a **disjoint**
      range so a case can be reversed by deleting exactly them.
    * ``key_type`` -- whether the payload keys arrive as ``str`` (what JSON
      gives today) or ``int`` (what the coercion makes harmless).
    * ``batched`` -- one multi-entry delta, or one delta per entry.

    Hypothesis is deliberately not used -- it is not a project dependency and
    CI installs only pytest. A seeded ``random.Random`` gives the same broad
    input coverage while keeping the run reproducible, following the
    ``generated_id_cases()`` idiom in ``tests/test_delete_id_coercion_v2.py``.
    """
    rnd = random.Random(seed)
    out = []
    for _ in range(cases):
        start_ids = rnd.sample(range(1, 500), rnd.choice([0, 1, rnd.randint(2, 6)]))
        replace_ids = []
        if start_ids and rnd.random() < 0.5:
            replace_ids = rnd.sample(start_ids, rnd.randint(1, len(start_ids)))
        new_ids = rnd.sample(range(500, 1000), rnd.randint(1, 4))
        out.append(
            (
                start_ids,
                replace_ids,
                new_ids,
                rnd.choice(["str", "int"]),
                rnd.choice([True, False]),
            )
        )
    return out


def generated_guard_cases(seed=20260802, cases=20):
    """Deterministic guard generator: ``(stale_ids, fresh_ids, present, absent)``.

    ``stale_ids`` and ``fresh_ids`` are drawn from the same range so they
    overlap arbitrarily -- including the case where the stale view is empty, and
    the case where it holds ids the server no longer has. ``present`` is always
    an id the *server* has; ``absent`` comes from a disjoint range, so it is in
    neither view.
    """
    rnd = random.Random(seed)
    out = []
    for _ in range(cases):
        fresh = rnd.sample(range(1, 200), rnd.randint(1, 6))
        stale = rnd.sample(range(1, 200), rnd.randint(0, 6))
        out.append((stale, fresh, rnd.choice(fresh), rnd.randint(1000, 9999)))
    return out


def generated_handler_sequences(seed=20260803, cases=15, steps=8):
    """Deterministic handler-call sequences: ``[(kind, ids, key_type), ...]``.

    A random interleaving of update and delete deltas over a small id space, so
    that adds, replacements, deletes of present ids, deletes of absent ids and
    deletes that empty the cache all occur -- which is what makes the sentinel
    invariance worth asserting step by step rather than only at the end.
    """
    rnd = random.Random(seed)
    out = []
    for _ in range(cases):
        ops = []
        for _ in range(steps):
            key_type = rnd.choice(["str", "int"])
            if rnd.random() < 0.5:
                ops.append(("update", rnd.sample(range(1, 20), rnd.randint(1, 3)), key_type))
            else:
                ops.append(("delete", [rnd.randint(1, 20)], key_type))
        out.append(ops)
    return out


def key_as(id_, key_type):
    """An id in the payload form the generated case asks for."""
    return id_ if key_type == "int" else str(id_)


def deliver_update(api, entries, batched):
    """Deliver ``entries`` as one multi-entry delta, or as one delta each."""
    if batched:
        api._event_update_monitor_into_list(dict(entries))
    else:
        for payload_key, entry in entries.items():
            api._event_update_monitor_into_list({payload_key: entry})


class TestGeneratedDeltaCoherence(unittest.TestCase):
    """Property 3 (Bug Condition): the delta handlers keep the cached monitor
    list coherent across generated cache states and payload shapes.

    Test 13, in two halves. The first is the forward direction -- whatever the
    starting state and however the payload is keyed or batched, the cache
    afterwards is exactly the merged dict. The second is the reverse -- deleting
    precisely what was added returns the cache to its starting value, which is
    the round trip the two handlers have to agree on: the update handler's
    ``str()`` coercion and the delete handler's have to land on the *same* key
    or a delete silently leaves the added entry behind.

    **Validates: Requirements 2.1, 2.3**
    """

    def test_generated_delta_payloads_merge_to_the_expected_cache(self):
        """Post-delta cache == the expected merged dict, for every case.

        **Validates: Requirements 2.1**
        """
        for start_ids, replace_ids, new_ids, key_type, batched in generated_delta_cases():
            with self.subTest(
                start=start_ids,
                replace=replace_ids,
                new=new_ids,
                keys=key_type,
                batched=batched,
            ):
                start = cache_of(*[monitor(i) for i in start_ids])
                api = make_handler_api(start)

                entries = {}
                expected = deepcopy(start)
                for id_ in replace_ids + new_ids:
                    entry = monitor(id_, name="delta {0}".format(id_))
                    entries[key_as(id_, key_type)] = entry
                    expected[str(id_)] = entry

                deliver_update(api, entries, batched)

                self.assertEqual(api._event_data[Event.MONITOR_LIST], expected)

    def test_deleting_everything_added_returns_the_cache_to_its_start(self):
        """Add ``new_ids``, then delete exactly those: back to the start.

        **Validates: Requirements 2.1, 2.3**
        """
        for start_ids, _replace_ids, new_ids, key_type, batched in generated_delta_cases():
            with self.subTest(
                start=start_ids, added=new_ids, keys=key_type, batched=batched
            ):
                start = cache_of(*[monitor(i) for i in start_ids])
                api = make_handler_api(start)
                entries = {key_as(i, key_type): monitor(i) for i in new_ids}

                deliver_update(api, entries, batched)
                self.assertEqual(
                    sorted(api._event_data[Event.MONITOR_LIST]),
                    sorted(str(i) for i in start_ids + new_ids),
                )

                for id_ in new_ids:
                    api._event_delete_monitor_from_list(key_as(id_, key_type))

                self.assertEqual(api._event_data[Event.MONITOR_LIST], start)


class TestGeneratedGuardCorrectness(unittest.TestCase):
    """Properties 3 and 4: across generated id sets, ``delete_monitor`` decides
    on the server's view and only on the server's view.

    The stale and fresh views are generated independently, so a case can have
    the target missing from the cache, or the cache carrying ids the server no
    longer has, or the cache empty -- and none of that may change the verdict.
    Both the int and the numeric-string form of every target are exercised,
    which is the #91 contract restated over a generated domain rather than the
    single hardcoded id.

    **Validates: Requirements 2.2, 3.3, 3.4**
    """

    @staticmethod
    def _api(stale_ids, fresh_ids):
        return make_guard_api(
            "delete_monitor",
            cache_of(*[monitor(i) for i in stale_ids]),
            cache_of(*[monitor(i) for i in fresh_ids]),
        )

    def test_sends_the_delete_for_every_id_the_server_has(self):
        """Target in ``fresh_ids``: delete sent, whatever the stale view held.

        **Validates: Requirements 2.2, 3.4**
        """
        for stale_ids, fresh_ids, present, _absent in generated_guard_cases():
            for target in (present, str(present)):
                with self.subTest(stale=stale_ids, fresh=fresh_ids, id_=target):
                    api, delete_monitor = self._api(stale_ids, fresh_ids)

                    try:
                        result = delete_monitor(target)
                    except UptimeKumaException as e:
                        self.fail(
                            "delete_monitor({0!r}) raised {1}(\"{2}\") although the "
                            "server has monitor {3}; _call events sent: {4}".format(
                                target, type(e).__name__, e, present, sent_events(api)
                            )
                        )

                    api._call.assert_any_call("deleteMonitor", present)
                    self.assertEqual(result, SERVER_RESPONSE)

    def test_rejects_every_id_neither_view_has_and_sends_nothing(self):
        """Target in neither view: still rejected, still nothing sent.

        **Validates: Requirements 3.3, 3.4**
        """
        for stale_ids, fresh_ids, _present, absent in generated_guard_cases():
            for target in (absent, str(absent)):
                with self.subTest(stale=stale_ids, fresh=fresh_ids, id_=target):
                    api, delete_monitor = self._api(stale_ids, fresh_ids)

                    with self.assertRaises(UptimeKumaException) as ctx:
                        delete_monitor(target)

                    self.assertEqual(str(ctx.exception), "monitor does not exist")
                    self.assertNotIsInstance(ctx.exception, (ValueError, Timeout))
                    self.assertNotIn("deleteMonitor", sent_events(api))


class TestGeneratedSentinelInvariance(unittest.TestCase):
    """Property 4 (Preservation): the ``{}`` zero-monitor sentinel keeps its
    meaning across generated handler call sequences.

    Two invariants, checked after **every** delta in the sequence rather than
    only at the end, because the failure mode is transient: a cache momentarily
    reset to ``None`` or emptied while monitors exist would make the very next
    read short-circuit the six monitor-scoped events to ``[]``.

    * once populated, the cache is never set back to ``None``;
    * the cache is ``{}`` exactly when the monitor count genuinely reached zero.

    **Validates: Requirements 3.5**
    """

    def test_cache_never_returns_to_none_and_empty_means_zero_monitors(self):
        """**Validates: Requirements 3.5**"""
        for ops in generated_handler_sequences():
            with self.subTest(ops=ops):
                api = make_handler_api(None)
                # the same state tracked independently of the handlers: None
                # before any delta populates it, then a plain dict
                model = None
                populated = False

                for kind, ids, key_type in ops:
                    if kind == "update":
                        deliver_update(
                            api,
                            {key_as(i, key_type): monitor(i) for i in ids},
                            batched=True,
                        )
                        model = {} if model is None else dict(model)
                        for id_ in ids:
                            model[str(id_)] = monitor(id_)
                    else:
                        api._event_delete_monitor_from_list(key_as(ids[0], key_type))
                        if model is not None:
                            model.pop(str(ids[0]), None)

                    cache = api._event_data[Event.MONITOR_LIST]
                    self.assertEqual(cache, model)

                    populated = populated or model is not None
                    if populated:
                        self.assertIsNotNone(
                            cache,
                            "the cache was set back to None after having been "
                            "populated, which no part of the fix may do: a later "
                            "read would then block until the timeout instead of "
                            "answering from the cache (op {0} {1})".format(kind, ids),
                        )
                        self.assertEqual(
                            cache == {},
                            not model,
                            "the {{}} zero-monitor sentinel must occur only when "
                            "the monitor count genuinely reached zero; "
                            "cache={0!r} expected={1!r} (op {2} {3})".format(
                                cache, model, kind, ids
                            ),
                        )


if __name__ == "__main__":
    unittest.main()
