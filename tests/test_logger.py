import unittest
import logging
from unittest.mock import patch, MagicMock

import socketio.exceptions

from uptime_kuma_api import Timeout, UptimeKumaException
from uptime_kuma_api.api import UptimeKumaApi


class TestLoggerParameter(unittest.TestCase):
    """Unit tests for the logger parameter in UptimeKumaApi.__init__."""

    @patch('uptime_kuma_api.api.UptimeKumaApi.connect')
    @patch('uptime_kuma_api.api.socketio.Client')
    def test_logger_none_omits_from_sio(self, mock_client_cls, mock_connect):
        """logger=None → socketio.Client called without logger kwarg (only ssl_verify)."""
        mock_sio = MagicMock()
        mock_client_cls.return_value = mock_sio

        UptimeKumaApi("http://fake:3001", logger=None)

        mock_client_cls.assert_called_once_with(ssl_verify=True)

    @patch('uptime_kuma_api.api.UptimeKumaApi.connect')
    @patch('uptime_kuma_api.api.socketio.Client')
    def test_logger_instance_passed_to_socketio(self, mock_client_cls, mock_connect):
        """logger=logging.getLogger("test") → socketio.Client called with logger=<Logger>."""
        mock_sio = MagicMock()
        mock_client_cls.return_value = mock_sio

        test_logger = logging.getLogger("test")
        UptimeKumaApi("http://fake:3001", logger=test_logger)

        mock_client_cls.assert_called_once_with(ssl_verify=True, logger=test_logger)

    @patch('uptime_kuma_api.api.UptimeKumaApi.connect')
    @patch('uptime_kuma_api.api.socketio.Client')
    def test_logger_bool_true_passed_to_socketio(self, mock_client_cls, mock_connect):
        """logger=True → socketio.Client called with logger=True (bool is valid)."""
        mock_sio = MagicMock()
        mock_client_cls.return_value = mock_sio

        UptimeKumaApi("http://fake:3001", logger=True)

        mock_client_cls.assert_called_once_with(ssl_verify=True, logger=True)

    def test_invalid_logger_int_raises_type_error(self):
        """logger=42 → TypeError raised before socketio.Client is created."""
        with self.assertRaises(TypeError) as ctx:
            UptimeKumaApi("http://fake:3001", logger=42)
        self.assertIn("logger must be a logging.Logger instance, a bool, or None", str(ctx.exception))

    def test_invalid_logger_string_raises_type_error(self):
        """logger="bad" → TypeError raised."""
        with self.assertRaises(TypeError) as ctx:
            UptimeKumaApi("http://fake:3001", logger="bad")
        self.assertIn("logger must be a logging.Logger instance, a bool, or None", str(ctx.exception))

    def test_invalid_logger_list_raises_type_error(self):
        """logger=[] → TypeError raised."""
        with self.assertRaises(TypeError) as ctx:
            UptimeKumaApi("http://fake:3001", logger=[])
        self.assertIn("logger must be a logging.Logger instance, a bool, or None", str(ctx.exception))


class TestCallTimeoutTranslationBugCondition(unittest.TestCase):
    """Bug E (#44) - socket.io timeouts leak the wrong exception type.

    Bug condition::

        isBugCondition_E(X) == raises(X, socketio.exceptions.TimeoutError)

    ``_call`` issues the transport call without translating transport errors::

        r = self.sio.call(event, data, timeout=self.timeout)

    ``socketio.exceptions.TimeoutError`` subclasses ``SocketIOError``, which is
    outside this library's exception hierarchy, so a caller catching
    ``UptimeKumaException`` (or the library's own ``Timeout``) does not catch a
    transport timeout. The wait helpers (``wait_for_event``,
    ``_get_event_data``) and ``get_status_page`` already raise the library
    ``Timeout``; ``_call`` is the outlier.

    Unit tests: no live server. ``socketio.Client`` and ``connect`` are patched
    exactly as in the logger tests above, and ``sio.call`` is given a
    ``socketio.exceptions.TimeoutError`` side effect, so only the exception
    translation in ``_call`` is under test.

    Property 9 (Bug Condition): when ``sio.call`` raises
    ``socketio.exceptions.TimeoutError``, ``_call`` must raise the library
    ``Timeout``, which is an ``UptimeKumaException``.

    **Validates: Requirements 1.8, 2.9**
    """

    # representative events reached through _call, with and without a payload
    CALL_INVOCATIONS = [
        ("getMonitorList", None),
        ("add", {"type": "http", "name": "monitor 1"}),
        ("deleteMonitor", 371),
    ]

    @patch('uptime_kuma_api.api.UptimeKumaApi.connect')
    @patch('uptime_kuma_api.api.socketio.Client')
    def _api_with_timing_out_transport(self, mock_client_cls, mock_connect):
        mock_sio = MagicMock()
        mock_sio.call.side_effect = socketio.exceptions.TimeoutError(
            "timed out waiting for callback"
        )
        mock_client_cls.return_value = mock_sio
        return UptimeKumaApi("http://fake:3001")

    def test_call_raises_library_timeout_on_transport_timeout(self):
        """_call must translate socketio TimeoutError into the library Timeout."""
        for event, data in self.CALL_INVOCATIONS:
            with self.subTest(event=event):
                api = self._api_with_timing_out_transport()

                with self.assertRaises(Timeout) as ctx:
                    api._call(event, data)

                self.assertIsInstance(ctx.exception, UptimeKumaException)
                api.sio.call.assert_called_once_with(
                    event, data, timeout=api.timeout
                )


class TestCallPreservation(unittest.TestCase):
    """Bug E (#44) preservation - everything that is NOT a transport timeout.

    Bug condition::

        isBugCondition_E(X) == raises(X, socketio.exceptions.TimeoutError)

    Only that condition may change. For every other ``_call`` invocation the
    fixed function must equal the original: the ``{"ok"}``-unwrapping return
    contract stays byte-for-byte, and any non-timeout transport error surfaces
    unchanged rather than being converted into a ``Timeout``.

    The ``_call`` return contract under test (``api.py`` ~561)::

        r = self.sio.call(event, data, timeout=self.timeout)
        if isinstance(r, dict) and "ok" in r:
            if not r["ok"]:
                raise UptimeKumaException(r.get("msg"))
            r.pop("ok")
        return r

    Unit tests: no live server. ``socketio.Client`` and ``connect`` are patched
    as in the classes above and ``sio.call`` is given a return value or a
    non-timeout side effect, so only ``_call``'s own logic is exercised.

    Property 10 (Preservation): a successful ``_call`` returns the same
    ``{"ok"}``-unwrapped result as before, and a non-timeout error surfaces
    unchanged (only ``TimeoutError`` is translated).

    **Validates: Requirements 3.7, 3.8**
    """

    @patch('uptime_kuma_api.api.UptimeKumaApi.connect')
    @patch('uptime_kuma_api.api.socketio.Client')
    def _api_with_transport(self, return_value, mock_client_cls, mock_connect):
        """API whose sio.call returns ``return_value``."""
        mock_sio = MagicMock()
        mock_sio.call.return_value = return_value
        mock_client_cls.return_value = mock_sio
        return UptimeKumaApi("http://fake:3001")

    @patch('uptime_kuma_api.api.UptimeKumaApi.connect')
    @patch('uptime_kuma_api.api.socketio.Client')
    def _api_with_failing_transport(self, exception, mock_client_cls, mock_connect):
        """API whose sio.call raises ``exception``."""
        mock_sio = MagicMock()
        mock_sio.call.side_effect = exception
        mock_client_cls.return_value = mock_sio
        return UptimeKumaApi("http://fake:3001")

    # --- successful calls: the {"ok"} unwrapping contract ---

    def test_dict_without_ok_key_returned_unchanged(self):
        """A plain dict with no "ok" key passes through untouched."""
        payload = {"monitor": {"id": 371, "name": "monitor 1"}}
        api = self._api_with_transport(payload)

        result = api._call("getMonitor", 371)

        self.assertEqual(result, {"monitor": {"id": 371, "name": "monitor 1"}})
        api.sio.call.assert_called_once_with("getMonitor", 371, timeout=api.timeout)

    def test_ok_true_is_popped_and_remainder_returned(self):
        """{"ok": True, ...} → "ok" removed, every other key preserved."""
        api = self._api_with_transport({"ok": True, "msg": "Added.", "monitorID": 371})

        result = api._call("add", {"type": "http", "name": "monitor 1"})

        self.assertEqual(result, {"msg": "Added.", "monitorID": 371})
        self.assertNotIn("ok", result)

    def test_ok_true_only_returns_empty_dict(self):
        """{"ok": True} with no other keys → empty dict (not None)."""
        api = self._api_with_transport({"ok": True})

        result = api._call("deleteMonitor", 371)

        self.assertEqual(result, {})

    def test_ok_false_raises_uptime_kuma_exception_with_msg(self):
        """{"ok": False, "msg": ...} → UptimeKumaException carrying that msg."""
        api = self._api_with_transport({"ok": False, "msg": "Monitor not found."})

        with self.assertRaises(UptimeKumaException) as ctx:
            api._call("deleteMonitor", 999)

        self.assertEqual(str(ctx.exception), "Monitor not found.")
        # a server-side failure is not a timeout
        self.assertNotIsInstance(ctx.exception, Timeout)

    def test_ok_false_without_msg_raises_with_none(self):
        """{"ok": False} with no msg → UptimeKumaException(None)."""
        api = self._api_with_transport({"ok": False})

        with self.assertRaises(UptimeKumaException) as ctx:
            api._call("deleteMonitor", 999)

        self.assertEqual(ctx.exception.args, (None,))

    def test_non_dict_returns_pass_through(self):
        """Non-dict returns (bool/list/str/int/None) are returned untouched."""
        for return_value in [True, False, None, 0, 371, "pong", [], [1, 2, 3]]:
            with self.subTest(return_value=return_value):
                api = self._api_with_transport(return_value)

                result = api._call("someEvent")

                self.assertIs(result, return_value)
                api.sio.call.assert_called_once_with(
                    "someEvent", None, timeout=api.timeout
                )

    def test_list_of_dicts_with_ok_keys_not_unwrapped(self):
        """A list is not a dict, so no "ok" unwrapping happens inside it."""
        payload = [{"ok": True, "id": 1}, {"ok": True, "id": 2}]
        api = self._api_with_transport(payload)

        result = api._call("getSomeList")

        self.assertEqual(result, [{"ok": True, "id": 1}, {"ok": True, "id": 2}])

    # --- non-timeout transport errors surface unchanged ---

    def test_non_timeout_transport_errors_surface_unchanged(self):
        """Only TimeoutError is translated; every other error propagates as-is."""
        non_timeout_errors = [
            socketio.exceptions.SocketIOError("transport blew up"),
            socketio.exceptions.BadNamespaceError("/ is not a connected namespace"),
            socketio.exceptions.DisconnectedError("client disconnected"),
            ValueError("not a socketio error at all"),
            RuntimeError("unexpected"),
        ]
        for error in non_timeout_errors:
            with self.subTest(error=type(error).__name__):
                api = self._api_with_failing_transport(error)

                with self.assertRaises(type(error)) as ctx:
                    api._call("getMonitorList")

                # same exception object, not wrapped or replaced
                self.assertIs(ctx.exception, error)
                # explicitly NOT translated into the library Timeout
                self.assertNotIsInstance(ctx.exception, Timeout)

    def test_socketio_error_is_not_converted_to_timeout(self):
        """SocketIOError is the TimeoutError parent - it must not be caught."""
        error = socketio.exceptions.SocketIOError("parent class, not a timeout")
        api = self._api_with_failing_transport(error)

        with self.assertRaises(socketio.exceptions.SocketIOError) as ctx:
            api._call("getMonitorList")

        self.assertIs(type(ctx.exception), socketio.exceptions.SocketIOError)
        self.assertNotIsInstance(ctx.exception, socketio.exceptions.TimeoutError)
        self.assertNotIsInstance(ctx.exception, UptimeKumaException)


if __name__ == '__main__':
    unittest.main()
