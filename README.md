# uptime-kuma-api2

A wrapper for the Uptime Kuma Socket.IO API — with full v2 support
---

> **About this project:** uptime-kuma-api2 is an independent continuation of
> [lucasheld/uptime-kuma-api](https://github.com/lucasheld/uptime-kuma-api),
> the original library created by [Lucas Held](https://github.com/lucasheld).
> That project appears to be unmaintained — its last release was in 2023, and
> open issues and pull requests (including several adding Uptime Kuma 2.x
> support) have sat unreviewed and unmerged. Rather than leave 2.x users
> without a working library, this project carries the code forward with full
> v2.x support while keeping backward compatibility with v1.x.
>
> It began as a fork and is published under the original MIT license. Lucas
> Held's copyright is retained in [LICENSE](LICENSE) alongside the later
> changes — full credit to him for building the foundation. This is a
> continuation, not a replacement: if the original project becomes active
> again, the changes here are available to contribute back upstream.

> **Naming:** the PyPI distribution is `uptime-kuma-api2`, while the import package remains `uptime_kuma_api` so existing code works unchanged. The similarly named PyPI projects `uptime-kuma-api` (the original) and `uptime-kuma-api-v2` (a different maintainer) are separate from this one. The repository was renamed from `uptime-kuma-api-v2` to `uptime-kuma-api2` to match the PyPI name; the old URL redirects automatically.

uptime-kuma-api2 is a Python wrapper for the [Uptime Kuma](https://github.com/louislam/uptime-kuma) Socket.IO API.

This package was originally developed to configure Uptime Kuma with Ansible. The original Ansible collection can be found at https://github.com/lucasheld/ansible-uptime-kuma.

Python version 3.8+ is required. Tested on 3.8 through 3.13.

Supported Uptime Kuma versions:

| Uptime Kuma     | uptime-kuma-api2 |
|-----------------|------------------|
| 2.0.0 - 2.4.0   | 2.0.0 - 2.2.1    |
| 1.21.3 - 1.23.2 | 1.0.0 - 1.2.1    |
| 1.17.0 - 1.21.2 | 0.1.0 - 0.13.0   |

Releases 1.2.1 and earlier were published under the upstream `uptime-kuma-api` name; 2.0.0 onward are published as `uptime-kuma-api2`.

Installation
---
uptime-kuma-api2 is available on the [Python Package Index (PyPI)](https://pypi.org/project/uptime-kuma-api2/).

You can install it using pip:

```
pip install uptime-kuma-api2
```

Documentation
---
The API reference is published on [Read the Docs](https://uptime-kuma-api2.readthedocs.io).

You can also build it locally with Sphinx:

```
pip install -r dev-requirements.txt
cd docs && make html
```

Note: [uptime-kuma-api.readthedocs.io](https://uptime-kuma-api.readthedocs.io) (without the `2`) is the *original* project's site and does not cover this project's v2 features.

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
{'msg': 'Added Successfully.', 'monitorID': 1}
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
The v2 unit tests need no live server. These are the tests CI runs:

```
pip install pytest
pytest tests/test_monitor_types_v2.py tests/test_monitor_params_v2.py tests/test_status_page_v2.py tests/test_notification_v2.py tests/test_logger.py tests/test_monitor_builder.py -v
```

The remaining test files are integration tests inherited from upstream. They expect a live Uptime Kuma instance at `http://127.0.0.1:3001` and will **delete all monitors, notifications, proxies, tags, status pages, docker hosts, maintenances and API keys** on that instance, so never point them at a production server.

Test files:

| File | Coverage |
|------|----------|
| `tests/test_monitor_types_v2.py` | New monitor types (RABBITMQ, SNMP, SMTP, SYSTEM_SERVICE) |
| `tests/test_monitor_params_v2.py` | v2 monitor parameters, version gating, validation |
| `tests/test_status_page_v2.py` | Status page analytics replacement, password removal, new fields |
| `tests/test_notification_v2.py` | Nextcloud Talk, Brevo, Evolution API providers |
| `tests/test_logger.py` | Logger parameter type validation |
| `tests/test_monitor_builder.py` | MonitorBuilder fluent API |
