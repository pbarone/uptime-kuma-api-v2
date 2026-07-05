import unittest
import logging
from unittest.mock import patch, MagicMock

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


if __name__ == '__main__':
    unittest.main()
