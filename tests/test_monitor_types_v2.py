import unittest
from unittest.mock import MagicMock

from uptime_kuma_api import MonitorType
from uptime_kuma_api.api import UptimeKumaApi, _check_arguments_monitor


class TestNewMonitorTypes(unittest.TestCase):
    """Unit tests for new v2 monitor types (RABBITMQ, SNMP, SMTP, SYSTEM_SERVICE).

    These tests exercise _build_monitor_data directly by mocking the version.
    They do NOT connect to a live server.
    """

    def setUp(self):
        # Create a mock instance that has the version property
        self.api = MagicMock(spec=UptimeKumaApi)
        self.api.version = "2.4.0"
        # Bind _build_monitor_data to our mock so self.version resolves
        self.build = UptimeKumaApi._build_monitor_data.__get__(self.api)

    # ─── RABBITMQ ────────────────────────────────────────────────────────────

    def test_rabbitmq_basic(self):
        """RABBITMQ with all required fields produces expected dict output."""
        result = self.build(
            type=MonitorType.RABBITMQ,
            name="test rabbitmq",
            rabbitmqNodes=["amqp://localhost:5672"],
        )
        assert result["type"] == MonitorType.RABBITMQ
        assert result["name"] == "test rabbitmq"
        # rabbitmqNodes is JSON-serialized
        assert '"amqp://localhost:5672"' in result["rabbitmqNodes"]
        assert result["rabbitmqUsername"] == ""
        assert result["rabbitmqPassword"] == ""

    def test_rabbitmq_with_credentials(self):
        """RABBITMQ with optional username/password includes them."""
        result = self.build(
            type=MonitorType.RABBITMQ,
            name="rabbitmq creds",
            rabbitmqNodes=["amqp://node1:5672", "amqp://node2:5672"],
            rabbitmqUsername="admin",
            rabbitmqPassword="secret",
        )
        assert result["rabbitmqUsername"] == "admin"
        assert result["rabbitmqPassword"] == "secret"
        # Multiple nodes serialized as JSON array
        assert "amqp://node1:5672" in result["rabbitmqNodes"]
        assert "amqp://node2:5672" in result["rabbitmqNodes"]

    def test_rabbitmq_missing_required_field(self):
        """RABBITMQ without rabbitmqNodes raises TypeError."""
        kwargs = {
            "type": MonitorType.RABBITMQ,
            "name": "test rabbitmq",
            "interval": 60,
            "maxretries": 1,
            "retryInterval": 60,
            "accepted_statuscodes": ["200-299"],
            "dns_resolve_type": "A",
        }
        with self.assertRaises(TypeError):
            _check_arguments_monitor(kwargs)

    # ─── SNMP ────────────────────────────────────────────────────────────────

    def test_snmp_basic(self):
        """SNMP with all required fields produces expected dict output."""
        result = self.build(
            type=MonitorType.SNMP,
            name="test snmp",
            hostname="192.168.1.1",
            snmpOid="1.3.6.1.2.1.1.1.0",
            snmpVersion="2c",
        )
        assert result["type"] == MonitorType.SNMP
        assert result["name"] == "test snmp"
        assert result["hostname"] == "192.168.1.1"
        assert result["snmpOid"] == "1.3.6.1.2.1.1.1.0"
        assert result["snmpVersion"] == "2c"

    def test_snmp_with_v3_username(self):
        """SNMP with optional snmp_v3_username includes it."""
        result = self.build(
            type=MonitorType.SNMP,
            name="snmp v3",
            hostname="10.0.0.1",
            snmpOid="1.3.6.1.2.1.1.3.0",
            snmpVersion="3",
            snmp_v3_username="snmpuser",
        )
        assert result["snmp_v3_username"] == "snmpuser"

    def test_snmp_missing_hostname(self):
        """SNMP without hostname raises TypeError."""
        kwargs = {
            "type": MonitorType.SNMP,
            "name": "test snmp",
            "interval": 60,
            "maxretries": 1,
            "retryInterval": 60,
            "snmpOid": "1.3.6.1.2.1.1.1.0",
            "accepted_statuscodes": ["200-299"],
            "dns_resolve_type": "A",
        }
        with self.assertRaises(TypeError):
            _check_arguments_monitor(kwargs)

    def test_snmp_missing_snmpOid(self):
        """SNMP without snmpOid raises TypeError."""
        kwargs = {
            "type": MonitorType.SNMP,
            "name": "test snmp",
            "interval": 60,
            "maxretries": 1,
            "retryInterval": 60,
            "hostname": "192.168.1.1",
            "accepted_statuscodes": ["200-299"],
            "dns_resolve_type": "A",
        }
        with self.assertRaises(TypeError):
            _check_arguments_monitor(kwargs)

    # ─── SMTP ────────────────────────────────────────────────────────────────

    def test_smtp_basic(self):
        """SMTP with all required fields produces expected dict output."""
        result = self.build(
            type=MonitorType.SMTP,
            name="test smtp",
            hostname="smtp.example.com",
        )
        assert result["type"] == MonitorType.SMTP
        assert result["name"] == "test smtp"
        assert result["hostname"] == "smtp.example.com"
        assert result["smtpSecurity"] == "starttls"  # default

    def test_smtp_custom_security(self):
        """SMTP with custom smtpSecurity includes it."""
        result = self.build(
            type=MonitorType.SMTP,
            name="smtp secure",
            hostname="smtp.example.com",
            smtpSecurity="secure",
        )
        assert result["smtpSecurity"] == "secure"

    def test_smtp_missing_hostname(self):
        """SMTP without hostname raises TypeError."""
        kwargs = {
            "type": MonitorType.SMTP,
            "name": "test smtp",
            "interval": 60,
            "maxretries": 1,
            "retryInterval": 60,
            "accepted_statuscodes": ["200-299"],
            "dns_resolve_type": "A",
        }
        with self.assertRaises(TypeError):
            _check_arguments_monitor(kwargs)

    # ─── SYSTEM_SERVICE ──────────────────────────────────────────────────────

    def test_system_service_basic(self):
        """SYSTEM_SERVICE with all required fields produces expected dict output."""
        result = self.build(
            type=MonitorType.SYSTEM_SERVICE,
            name="test svc",
            system_service_name="nginx",
        )
        assert result["type"] == MonitorType.SYSTEM_SERVICE
        assert result["name"] == "test svc"
        assert result["system_service_name"] == "nginx"

    def test_system_service_missing_service_name(self):
        """SYSTEM_SERVICE without system_service_name raises TypeError."""
        kwargs = {
            "type": MonitorType.SYSTEM_SERVICE,
            "name": "test svc",
            "interval": 60,
            "maxretries": 1,
            "retryInterval": 60,
            "accepted_statuscodes": ["200-299"],
            "dns_resolve_type": "A",
        }
        with self.assertRaises(TypeError):
            _check_arguments_monitor(kwargs)

    # ─── Port Defaults ───────────────────────────────────────────────────────

    def test_snmp_default_port(self):
        """SNMP type defaults port to 161 when not specified."""
        result = self.build(
            type=MonitorType.SNMP,
            name="snmp port",
            hostname="10.0.0.1",
            snmpOid="1.3.6.1.2.1.1.1.0",
            snmpVersion="2c",
        )
        assert result["port"] == 161

    def test_smtp_default_port(self):
        """SMTP type defaults port to 25 when not specified."""
        result = self.build(
            type=MonitorType.SMTP,
            name="smtp port",
            hostname="smtp.example.com",
        )
        assert result["port"] == 25

    def test_snmp_explicit_port_overrides_default(self):
        """SNMP with explicit port does not get overridden to 161."""
        result = self.build(
            type=MonitorType.SNMP,
            name="snmp custom port",
            hostname="10.0.0.1",
            port=162,
            snmpOid="1.3.6.1.2.1.1.1.0",
            snmpVersion="2c",
        )
        assert result["port"] == 162

    def test_smtp_explicit_port_overrides_default(self):
        """SMTP with explicit port does not get overridden to 25."""
        result = self.build(
            type=MonitorType.SMTP,
            name="smtp custom port",
            hostname="smtp.example.com",
            port=587,
        )
        assert result["port"] == 587


if __name__ == "__main__":
    unittest.main()
