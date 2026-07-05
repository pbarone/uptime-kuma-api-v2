# uptime-kuma-api-v2

A wrapper for the Uptime Kuma Socket.IO API — with full v2 support
---

> **Fork notice:** This is an actively maintained fork of [lucasheld/uptime-kuma-api](https://github.com/lucasheld/uptime-kuma-api), which appears to be unmaintained (last release: 2023, open PRs unanswered). This fork adds full Uptime Kuma v2.x support while maintaining backward compatibility with v1.x. Original work by [Lucas Held](https://github.com/lucasheld) — thank you for building the foundation.

uptime-kuma-api-v2 is a Python wrapper for the [Uptime Kuma](https://github.com/louislam/uptime-kuma) Socket.IO API.

This package was originally developed to configure Uptime Kuma with Ansible. The original Ansible collection can be found at https://github.com/lucasheld/ansible-uptime-kuma.

Python version 3.7+ is required.

Supported Uptime Kuma versions:

| Uptime Kuma     | uptime-kuma-api |
|-----------------|-----------------|
| 2.0.0 - 2.4.0   | 2.0.0 - 2.1.0   |
| 1.21.3 - 1.23.2 | 1.0.0 - 1.2.1   |
| 1.17.0 - 1.21.2 | 0.1.0 - 0.13.0  |

Installation
---
uptime-kuma-api2 is available on the [Python Package Index (PyPI)](https://pypi.org/project/uptime-kuma-api2/).

You can install it using pip:

```
pip install uptime-kuma-api2
```

Documentation
---
The API Reference is available on [Read the Docs](https://uptime-kuma-api.readthedocs.io).

Example
---
Once you have installed the python package, you can use it to communicate with an Uptime Kuma instance.

To do so, import `UptimeKumaApi` from the library and specify the Uptime Kuma server url (e.g. 'http://127.0.0.1:3001'), username and password to initialize the connection.

```python
>>> from uptime_kuma_api import UptimeKumaApi, MonitorType
>>> api = UptimeKumaApi('INSERT_URL')
>>> api.login('INSERT_USERNAME', 'INSERT_PASSWORD')
```

Now you can call one of the existing methods of the instance. For example create a new monitor:

```python
>>> result = api.add_monitor(type=MonitorType.HTTP, name="Google", url="https://google.com")
>>> print(result)
{'msg': 'Added Successfully.', 'monitorId': 1}
```

At the end, the connection to the API must be disconnected so that the program does not block.

```python
>>> api.disconnect()
```

With a context manager, the disconnect method is called automatically:

```python
from uptime_kuma_api import UptimeKumaApi

with UptimeKumaApi('INSERT_URL') as api:
    api.login('INSERT_USERNAME', 'INSERT_PASSWORD')
    api.add_monitor(
        type=MonitorType.HTTP,
        name="Google",
        url="https://google.com"
    )
```

MonitorBuilder
---
For complex monitor configurations, use the fluent `MonitorBuilder`:

```python
from uptime_kuma_api import UptimeKumaApi, MonitorType, MonitorBuilder

with UptimeKumaApi('INSERT_URL') as api:
    api.login('INSERT_USERNAME', 'INSERT_PASSWORD')
    
    config = (
        MonitorBuilder()
        .type(MonitorType.HTTP)
        .name("My Monitor")
        .url("https://example.com")
        .interval(60)
        .conditions([
            {"type": "expression", "variable": "response_status", "operator": "==", "value": "200", "andOr": ""}
        ])
        .build()
    )
    result = api.add_monitor(**config)
    print(result)
```

New in v2.1.0
---
- **New monitor types**: RabbitMQ, SNMP, SMTP, System Service
- **New notification providers**: Nextcloud Talk, Brevo, Evolution API
- **MonitorBuilder**: Fluent builder pattern for monitor configuration
- **Logger support**: Pass a custom logger for Socket.IO debugging
- **v2-only parameters**: Automatic version gating ensures backward compatibility with v1.x

Testing
---
Unit tests cover all v2 features and can be run without a live server:

```
pip install pytest
pytest tests/ -v
```

Test files:

| File | Coverage |
|------|----------|
| `tests/test_monitor_types_v2.py` | New monitor types (RABBITMQ, SNMP, SMTP, SYSTEM_SERVICE) |
| `tests/test_monitor_params_v2.py` | v2 monitor parameters, version gating, validation |
| `tests/test_status_page_v2.py` | Status page analytics replacement, password removal, new fields |
| `tests/test_notification_v2.py` | Nextcloud Talk, Brevo, Evolution API providers |
| `tests/test_logger.py` | Logger parameter type validation |
| `tests/test_monitor_builder.py` | MonitorBuilder fluent API |
