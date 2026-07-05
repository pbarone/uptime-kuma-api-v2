import unittest

from uptime_kuma_api import MonitorType, MonitorBuilder


class TestMonitorBuilder(unittest.TestCase):
    def test_chaining_returns_self(self):
        b = MonitorBuilder()
        assert b.type(MonitorType.HTTP) is b
        assert b.name("x") is b
        assert b.url("http://x.com") is b

    def test_build_with_type_and_name(self):
        result = MonitorBuilder().type(MonitorType.HTTP).name("test").build()
        assert result == {"type": MonitorType.HTTP, "name": "test"}

    def test_build_missing_type_raises(self):
        with self.assertRaises(ValueError) as ctx:
            MonitorBuilder().name("test").build()
        assert "type" in str(ctx.exception)

    def test_build_missing_name_raises(self):
        with self.assertRaises(ValueError) as ctx:
            MonitorBuilder().type(MonitorType.HTTP).build()
        assert "name" in str(ctx.exception)

    def test_build_missing_both_raises(self):
        with self.assertRaises(ValueError) as ctx:
            MonitorBuilder().build()
        assert "type" in str(ctx.exception)
        assert "name" in str(ctx.exception)

    def test_last_set_wins(self):
        result = MonitorBuilder().type(MonitorType.HTTP).name("first").name("second").build()
        assert result["name"] == "second"

    def test_type_is_enum_not_string(self):
        result = MonitorBuilder().type(MonitorType.PING).name("test").build()
        assert result["type"] is MonitorType.PING
        assert not isinstance(result["type"], str) or isinstance(result["type"], MonitorType)

    def test_only_set_fields_in_output(self):
        result = MonitorBuilder().type(MonitorType.HTTP).name("test").url("http://x.com").build()
        assert set(result.keys()) == {"type", "name", "url"}

    def test_multiple_fields(self):
        result = (
            MonitorBuilder()
            .type(MonitorType.DNS)
            .name("dns check")
            .hostname("example.com")
            .dns_resolve_server("8.8.8.8")
            .dns_resolve_type("AAAA")
            .interval(120)
            .build()
        )
        assert result == {
            "type": MonitorType.DNS,
            "name": "dns check",
            "hostname": "example.com",
            "dns_resolve_server": "8.8.8.8",
            "dns_resolve_type": "AAAA",
            "interval": 120,
        }
