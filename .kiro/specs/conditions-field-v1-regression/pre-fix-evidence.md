# Pre-fix evidence — requirement 2.9

Requirement 2.9 demands the regression tests be *demonstrated to fail against
the unfixed code before the fix lands*. This file is that artifact for tasks
1-2 → 3: the verbatim pre-fix failure of all six tests in
`TestConditionsV1Gate` (`tests/test_monitor_params_v2.py`).

Copy the "Verbatim pytest output" section below into the PR description when the
fix is raised. **The fix must not land without it.**

## Provenance

| | |
|---|---|
| Recorded by | task 3 of the `conditions-field-v1-regression` bugfix spec |
| Code state | **unfixed** — `conditions` still assigned in the unconditional common `data` dict at `api.py:968`; no `_check_conditions_supported` helper exists anywhere |
| Command | `.venv\Scripts\python.exe -m pytest tests/test_monitor_params_v2.py -v -k TestConditionsV1Gate` |
| Environment | Windows, Python 3.13.3, pytest 9.1.1, pluggy 1.6.0 |
| Result | **11 failed, 1 passed, 53 deselected in 0.79s**, exit code 1 — the expected outcome |

On the counts: the six selected tests all failed. `test_conditions_omitted_on_v1_all_types`
uses `subTest`, and pytest 9 reports each of its six subtest failures as its own
`SUBFAILED` line while the parent test id is still printed `PASSED`. That single
`passed` is the subtest parent, not a test that behaved correctly — every one of
its six monitor types is in the `SUBFAILED` list below with its own
counterexample payload. `11 failed` = 5 plain failures + 6 subtest failures.

## Verdict

All six tests failed, and all six failed for the right reason.

| Test | Failure | Reason verified |
|---|---|---|
| `test_conditions_omitted_on_v1` | `AssertionError: 'conditions' unexpectedly found in {...}` | `AssertionError` from the intended `assertNotIn`, payload shows `'conditions': []` |
| `test_conditions_omitted_on_v1_all_types` | 6× `SUBFAILED` — HTTP, PING, PORT, DNS, KEYWORD, PUSH | same `AssertionError`, `'conditions': []` in every one of the six payloads |
| `test_conditions_empty_list_omitted_on_v1` | `AssertionError: 'conditions' unexpectedly found in {...}` | same, with `conditions=[]` supplied explicitly — no raise occurred, only the key-presence half failed, which is the designed boundary behaviour |
| `test_explicit_conditions_raises_on_v1` | `AssertionError: UptimeKumaException not raised` | no exception at all — the field is silently forwarded |
| `test_edit_monitor_explicit_conditions_raises_on_v1` | `AssertionError: UptimeKumaException not raised` | no exception at all; traceback is the `assertRaises` context manager exiting, not a mock-binding error |
| `test_builder_conditions_raises_on_v1` | `AssertionError: UptimeKumaException not raised` | no exception at all; the `assertEqual(config["conditions"], ...)` line above it passed, so the builder did emit the kwarg and the v1 build accepted it |

**Failure reason verified, not just the failure.** Task 3 requires each task-1
failure to be an `AssertionError` showing `conditions: []` in the payload rather
than an `AttributeError` or `TypeError` from harness drift, and each task-2
failure to be "`UptimeKumaException` not raised" rather than an error from a
mis-bound mock. Confirmed on both counts:

- No `AttributeError` and no `TypeError` appears anywhere in the output. The
  harness resolved against pre-fix names only.
- Every task-1 failure prints the full offending payload with `'conditions': []`
  sitting between `'httpBodyEncoding': 'json'` and `'parent': None` — i.e. at its
  literal position in the common `data` dict (`api.py:968`), which is the direct
  visual confirmation of root cause 1.
- Every task-2 failure is the bare `assertRaises` "not raised" message. The
  `_build_monitor_data` and `edit_monitor` calls ran to completion and returned
  normally, which is root cause 3 (nothing downstream gates the field) and root
  cause 4 (`edit_monitor` bypasses `_build_monitor_data` and has no guard of its
  own).

## One harness correction made during this task

`test_edit_monitor_explicit_conditions_raises_on_v1` initially failed with
`KeyError: 'dns_resolve_type'` raised from `_check_arguments_monitor`
(`api.py:329`), reached via `edit_monitor` at `api.py:1795`. That is a
wrong-reason failure: the mocked `get_monitor` return value was missing a key
that `_check_arguments_monitor` reads unconditionally, so the test died on
harness drift before it could demonstrate the absent guard.

Per task 3's instruction ("any other failure mode means task 1 or 2 needs
correcting, not the code"), the **test harness only** was corrected —
`"dns_resolve_type": "A"` was added to the mocked `get_monitor` payload in
`tests/test_monitor_params_v2.py`. No production file was touched. After the
correction the test fails with the required `UptimeKumaException not raised`.

This detail matters post-fix too: once the guard is added in task 5.2 it raises
*before* `get_monitor(id_)`, so the mocked payload is never validated and the
extra key becomes inert. It is needed only to make the pre-fix run reach the
assertion.

## Counterexamples

The counterexample is the payload itself — no exotic input is required, which is
the whole severity argument for this bug. On a `1.23.2` mock:

- `_build_monitor_data(type=HTTP, name="t", url="http://x")` →
  `'conditions': []` present. **No caller opt-in whatsoever.**
- The same for PING, PORT, DNS, KEYWORD and PUSH — the defect is not confined to
  one monitor type.
- `conditions=[]` → key still present (`[]`), no raise.
- `conditions=[{"type": "expression", "expression": {...}}]` → key present with
  the caller's list, **no exception**, so the value is forwarded to a server
  whose schema has no such column.
- `edit_monitor(7, conditions=[...])` → merged dict carries the key through with
  no exception raised.
- `MonitorBuilder().type(HTTP).name("t").url("http://x").conditions([...]).build()`
  splatted into the v1 build → identical, confirming the builder route reaches
  the server the same way an explicit kwarg does.

Against a real 1.23.x server each of these is the
`SQLITE_ERROR: table monitor has no column named conditions` insert rejection
recorded in `bugfix.md`.

## Verbatim pytest output

```
============================= test session starts =============================
platform win32 -- Python 3.13.3, pytest-9.1.1, pluggy-1.6.0 -- F:\Dev\uptime-kuma-api-v2\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: F:\Dev\uptime-kuma-api-v2
collecting ... collected 59 items / 53 deselected / 6 selected

tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_builder_conditions_raises_on_v1 FAILED [ 16%]
tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_conditions_empty_list_omitted_on_v1 FAILED [ 33%]
tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_conditions_omitted_on_v1 FAILED [ 50%]
tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_conditions_omitted_on_v1_all_types 
tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_conditions_omitted_on_v1_all_types PASSED [ 66%]
tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_edit_monitor_explicit_conditions_raises_on_v1 FAILED [ 83%]
tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_explicit_conditions_raises_on_v1 FAILED [100%]

================================== FAILURES ===================================
__________ TestConditionsV1Gate.test_builder_conditions_raises_on_v1 __________

self = <test_monitor_params_v2.TestConditionsV1Gate testMethod=test_builder_conditions_raises_on_v1>

    def test_builder_conditions_raises_on_v1(self):
        """A MonitorBuilder-built config carrying conditions raises on v1.
    
        ``MonitorBuilder`` holds a plain dict with no server connection, so it
        is version-blind by design and cannot enforce this itself. Its output
        can only reach a server through ``add_monitor`` / ``edit_monitor``, so
        this test pins the enforcement boundary there rather than in the
        builder -- which is what lets the builder stay unchanged.
    
        **Validates: Requirements 2.4**
        """
        config = (
            MonitorBuilder()
            .type(MonitorType.HTTP)
            .name("t")
            .url("http://x")
            .conditions(SAMPLE_CONDITIONS)
            .build()
        )
        self.assertEqual(config["conditions"], SAMPLE_CONDITIONS)
    
        build = self._build_v1()
    
>       with self.assertRaises(UptimeKumaException) as ctx:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: UptimeKumaException not raised

tests\test_monitor_params_v2.py:1263: AssertionError
________ TestConditionsV1Gate.test_conditions_empty_list_omitted_on_v1 ________

self = <test_monitor_params_v2.TestConditionsV1Gate testMethod=test_conditions_empty_list_omitted_on_v1>

    def test_conditions_empty_list_omitted_on_v1(self):
        """conditions=[] on v1 raises nothing and emits no key.
    
        An explicit empty list is indistinguishable in effect from the default,
        so it is deliberately outside the bug condition: it is treated as "no
        conditions requested" and simply omitted rather than rejected. This is
        the case that pins the guard on truthiness rather than ``is not None``.
    
        **Validates: Requirements 2.1, 2.2**
        """
        result = self._build_v1()(
            type=MonitorType.HTTP,
            name="t",
            url="http://x",
            conditions=[],
        )
>       self.assertNotIn("conditions", result)
E       AssertionError: 'conditions' unexpectedly found in {'type': <MonitorType.HTTP: 'http'>, 'name': 't', 'interval': 60, 'retryInterval': 60, 'maxretries': 1, 'notificationIDList': [], 'upsideDown': False, 'resendInterval': 0, 'description': None, 'httpBodyEncoding': 'json', 'conditions': [], 'parent': None, 'url': 'http://x', 'maxredirects': 10, 'accepted_statuscodes': ['200-299'], 'expiryNotification': False, 'ignoreTls': False, 'proxyId': None, 'method': 'GET', 'body': None, 'headers': None, 'authMethod': <AuthMethod.NONE: ''>, 'timeout': 48, 'hostname': None, 'packetSize': 56, 'port': None, 'dns_resolve_server': '1.1.1.1', 'dns_resolve_type': 'A', 'mqttUsername': '', 'mqttPassword': '', 'mqttTopic': '', 'mqttSuccessMessage': '', 'databaseConnectionString': None}

tests\test_monitor_params_v2.py:1165: AssertionError
_____________ TestConditionsV1Gate.test_conditions_omitted_on_v1 ______________

self = <test_monitor_params_v2.TestConditionsV1Gate testMethod=test_conditions_omitted_on_v1>

    def test_conditions_omitted_on_v1(self):
        """conditions is absent from a v1 payload when not supplied.
    
        This is the minimal, most direct encoding of the regression: the
        default ``add_monitor`` path against a 1.23.x server.
    
        **Validates: Requirements 2.1, 2.2**
        """
        result = self._build_v1()(
            type=MonitorType.HTTP,
            name="t",
            url="http://x",
        )
>       self.assertNotIn("conditions", result)
E       AssertionError: 'conditions' unexpectedly found in {'type': <MonitorType.HTTP: 'http'>, 'name': 't', 'interval': 60, 'retryInterval': 60, 'maxretries': 1, 'notificationIDList': [], 'upsideDown': False, 'resendInterval': 0, 'description': None, 'httpBodyEncoding': 'json', 'conditions': [], 'parent': None, 'url': 'http://x', 'maxredirects': 10, 'accepted_statuscodes': ['200-299'], 'expiryNotification': False, 'ignoreTls': False, 'proxyId': None, 'method': 'GET', 'body': None, 'headers': None, 'authMethod': <AuthMethod.NONE: ''>, 'timeout': 48, 'hostname': None, 'packetSize': 56, 'port': None, 'dns_resolve_server': '1.1.1.1', 'dns_resolve_type': 'A', 'mqttUsername': '', 'mqttPassword': '', 'mqttTopic': '', 'mqttSuccessMessage': '', 'databaseConnectionString': None}

tests\test_monitor_params_v2.py:1120: AssertionError
_ TestConditionsV1Gate.test_conditions_omitted_on_v1_all_types (type=<MonitorType.HTTP: 'http'>) _

self = <test_monitor_params_v2.TestConditionsV1Gate testMethod=test_conditions_omitted_on_v1_all_types>

    def test_conditions_omitted_on_v1_all_types(self):
        """conditions is absent on v1 for every monitor type, unconditionally.
    
        Direct evidence that the defect needs no opt-in and is not confined to
        one monitor type.
    
        **Validates: Requirements 2.1, 2.2**
        """
        cases = {
            MonitorType.HTTP: dict(url="http://x"),
            MonitorType.PING: dict(hostname="127.0.0.1"),
            MonitorType.PORT: dict(hostname="127.0.0.1", port=8080),
            MonitorType.DNS: dict(
                hostname="example.com",
                dns_resolve_server="1.1.1.1",
                port=53,
            ),
            MonitorType.KEYWORD: dict(url="http://x", keyword="ok"),
            MonitorType.PUSH: dict(),
        }
        for type_, kwargs in cases.items():
            with self.subTest(type=type_):
                result = self._build_v1()(type=type_, name="t", **kwargs)
>               self.assertNotIn("conditions", result)
E               AssertionError: 'conditions' unexpectedly found in {'type': <MonitorType.HTTP: 'http'>, 'name': 't', 'interval': 60, 'retryInterval': 60, 'maxretries': 1, 'notificationIDList': [], 'upsideDown': False, 'resendInterval': 0, 'description': None, 'httpBodyEncoding': 'json', 'conditions': [], 'parent': None, 'url': 'http://x', 'maxredirects': 10, 'accepted_statuscodes': ['200-299'], 'expiryNotification': False, 'ignoreTls': False, 'proxyId': None, 'method': 'GET', 'body': None, 'headers': None, 'authMethod': <AuthMethod.NONE: ''>, 'timeout': 48, 'hostname': None, 'packetSize': 56, 'port': None, 'dns_resolve_server': '1.1.1.1', 'dns_resolve_type': 'A', 'mqttUsername': '', 'mqttPassword': '', 'mqttTopic': '', 'mqttSuccessMessage': '', 'databaseConnectionString': None}

tests\test_monitor_params_v2.py:1145: AssertionError
_ TestConditionsV1Gate.test_conditions_omitted_on_v1_all_types (type=<MonitorType.PING: 'ping'>) _

self = <test_monitor_params_v2.TestConditionsV1Gate testMethod=test_conditions_omitted_on_v1_all_types>

    def test_conditions_omitted_on_v1_all_types(self):
        """conditions is absent on v1 for every monitor type, unconditionally.
    
        Direct evidence that the defect needs no opt-in and is not confined to
        one monitor type.
    
        **Validates: Requirements 2.1, 2.2**
        """
        cases = {
            MonitorType.HTTP: dict(url="http://x"),
            MonitorType.PING: dict(hostname="127.0.0.1"),
            MonitorType.PORT: dict(hostname="127.0.0.1", port=8080),
            MonitorType.DNS: dict(
                hostname="example.com",
                dns_resolve_server="1.1.1.1",
                port=53,
            ),
            MonitorType.KEYWORD: dict(url="http://x", keyword="ok"),
            MonitorType.PUSH: dict(),
        }
        for type_, kwargs in cases.items():
            with self.subTest(type=type_):
                result = self._build_v1()(type=type_, name="t", **kwargs)
>               self.assertNotIn("conditions", result)
E               AssertionError: 'conditions' unexpectedly found in {'type': <MonitorType.PING: 'ping'>, 'name': 't', 'interval': 60, 'retryInterval': 60, 'maxretries': 1, 'notificationIDList': [], 'upsideDown': False, 'resendInterval': 0, 'description': None, 'httpBodyEncoding': 'json', 'conditions': [], 'parent': None, 'url': None, 'maxredirects': 10, 'accepted_statuscodes': ['200-299'], 'expiryNotification': False, 'ignoreTls': False, 'proxyId': None, 'method': 'GET', 'body': None, 'headers': None, 'authMethod': <AuthMethod.NONE: ''>, 'timeout': 48, 'hostname': '127.0.0.1', 'packetSize': 56, 'port': None, 'dns_resolve_server': '1.1.1.1', 'dns_resolve_type': 'A', 'mqttUsername': '', 'mqttPassword': '', 'mqttTopic': '', 'mqttSuccessMessage': '', 'databaseConnectionString': None}

tests\test_monitor_params_v2.py:1145: AssertionError
_ TestConditionsV1Gate.test_conditions_omitted_on_v1_all_types (type=<MonitorType.PORT: 'port'>) _

self = <test_monitor_params_v2.TestConditionsV1Gate testMethod=test_conditions_omitted_on_v1_all_types>

    def test_conditions_omitted_on_v1_all_types(self):
        """conditions is absent on v1 for every monitor type, unconditionally.
    
        Direct evidence that the defect needs no opt-in and is not confined to
        one monitor type.
    
        **Validates: Requirements 2.1, 2.2**
        """
        cases = {
            MonitorType.HTTP: dict(url="http://x"),
            MonitorType.PING: dict(hostname="127.0.0.1"),
            MonitorType.PORT: dict(hostname="127.0.0.1", port=8080),
            MonitorType.DNS: dict(
                hostname="example.com",
                dns_resolve_server="1.1.1.1",
                port=53,
            ),
            MonitorType.KEYWORD: dict(url="http://x", keyword="ok"),
            MonitorType.PUSH: dict(),
        }
        for type_, kwargs in cases.items():
            with self.subTest(type=type_):
                result = self._build_v1()(type=type_, name="t", **kwargs)
>               self.assertNotIn("conditions", result)
E               AssertionError: 'conditions' unexpectedly found in {'type': <MonitorType.PORT: 'port'>, 'name': 't', 'interval': 60, 'retryInterval': 60, 'maxretries': 1, 'notificationIDList': [], 'upsideDown': False, 'resendInterval': 0, 'description': None, 'httpBodyEncoding': 'json', 'conditions': [], 'parent': None, 'url': None, 'maxredirects': 10, 'accepted_statuscodes': ['200-299'], 'expiryNotification': False, 'ignoreTls': False, 'proxyId': None, 'method': 'GET', 'body': None, 'headers': None, 'authMethod': <AuthMethod.NONE: ''>, 'timeout': 48, 'hostname': '127.0.0.1', 'packetSize': 56, 'port': 8080, 'dns_resolve_server': '1.1.1.1', 'dns_resolve_type': 'A', 'mqttUsername': '', 'mqttPassword': '', 'mqttTopic': '', 'mqttSuccessMessage': '', 'databaseConnectionString': None}

tests\test_monitor_params_v2.py:1145: AssertionError
_ TestConditionsV1Gate.test_conditions_omitted_on_v1_all_types (type=<MonitorType.DNS: 'dns'>) _

self = <test_monitor_params_v2.TestConditionsV1Gate testMethod=test_conditions_omitted_on_v1_all_types>

    def test_conditions_omitted_on_v1_all_types(self):
        """conditions is absent on v1 for every monitor type, unconditionally.
    
        Direct evidence that the defect needs no opt-in and is not confined to
        one monitor type.
    
        **Validates: Requirements 2.1, 2.2**
        """
        cases = {
            MonitorType.HTTP: dict(url="http://x"),
            MonitorType.PING: dict(hostname="127.0.0.1"),
            MonitorType.PORT: dict(hostname="127.0.0.1", port=8080),
            MonitorType.DNS: dict(
                hostname="example.com",
                dns_resolve_server="1.1.1.1",
                port=53,
            ),
            MonitorType.KEYWORD: dict(url="http://x", keyword="ok"),
            MonitorType.PUSH: dict(),
        }
        for type_, kwargs in cases.items():
            with self.subTest(type=type_):
                result = self._build_v1()(type=type_, name="t", **kwargs)
>               self.assertNotIn("conditions", result)
E               AssertionError: 'conditions' unexpectedly found in {'type': <MonitorType.DNS: 'dns'>, 'name': 't', 'interval': 60, 'retryInterval': 60, 'maxretries': 1, 'notificationIDList': [], 'upsideDown': False, 'resendInterval': 0, 'description': None, 'httpBodyEncoding': 'json', 'conditions': [], 'parent': None, 'url': None, 'maxredirects': 10, 'accepted_statuscodes': ['200-299'], 'expiryNotification': False, 'ignoreTls': False, 'proxyId': None, 'method': 'GET', 'body': None, 'headers': None, 'authMethod': <AuthMethod.NONE: ''>, 'timeout': 48, 'hostname': 'example.com', 'packetSize': 56, 'port': 53, 'dns_resolve_server': '1.1.1.1', 'dns_resolve_type': 'A', 'mqttUsername': '', 'mqttPassword': '', 'mqttTopic': '', 'mqttSuccessMessage': '', 'databaseConnectionString': None}

tests\test_monitor_params_v2.py:1145: AssertionError
_ TestConditionsV1Gate.test_conditions_omitted_on_v1_all_types (type=<MonitorType.KEYWORD: 'keyword'>) _

self = <test_monitor_params_v2.TestConditionsV1Gate testMethod=test_conditions_omitted_on_v1_all_types>

    def test_conditions_omitted_on_v1_all_types(self):
        """conditions is absent on v1 for every monitor type, unconditionally.
    
        Direct evidence that the defect needs no opt-in and is not confined to
        one monitor type.
    
        **Validates: Requirements 2.1, 2.2**
        """
        cases = {
            MonitorType.HTTP: dict(url="http://x"),
            MonitorType.PING: dict(hostname="127.0.0.1"),
            MonitorType.PORT: dict(hostname="127.0.0.1", port=8080),
            MonitorType.DNS: dict(
                hostname="example.com",
                dns_resolve_server="1.1.1.1",
                port=53,
            ),
            MonitorType.KEYWORD: dict(url="http://x", keyword="ok"),
            MonitorType.PUSH: dict(),
        }
        for type_, kwargs in cases.items():
            with self.subTest(type=type_):
                result = self._build_v1()(type=type_, name="t", **kwargs)
>               self.assertNotIn("conditions", result)
E               AssertionError: 'conditions' unexpectedly found in {'type': <MonitorType.KEYWORD: 'keyword'>, 'name': 't', 'interval': 60, 'retryInterval': 60, 'maxretries': 1, 'notificationIDList': [], 'upsideDown': False, 'resendInterval': 0, 'description': None, 'httpBodyEncoding': 'json', 'conditions': [], 'parent': None, 'keyword': 'ok', 'invertKeyword': False, 'url': 'http://x', 'maxredirects': 10, 'accepted_statuscodes': ['200-299'], 'expiryNotification': False, 'ignoreTls': False, 'proxyId': None, 'method': 'GET', 'body': None, 'headers': None, 'authMethod': <AuthMethod.NONE: ''>, 'timeout': 48, 'hostname': None, 'packetSize': 56, 'port': None, 'dns_resolve_server': '1.1.1.1', 'dns_resolve_type': 'A', 'mqttUsername': '', 'mqttPassword': '', 'mqttTopic': '', 'mqttSuccessMessage': '', 'databaseConnectionString': None}

tests\test_monitor_params_v2.py:1145: AssertionError
_ TestConditionsV1Gate.test_conditions_omitted_on_v1_all_types (type=<MonitorType.PUSH: 'push'>) _

self = <test_monitor_params_v2.TestConditionsV1Gate testMethod=test_conditions_omitted_on_v1_all_types>

    def test_conditions_omitted_on_v1_all_types(self):
        """conditions is absent on v1 for every monitor type, unconditionally.
    
        Direct evidence that the defect needs no opt-in and is not confined to
        one monitor type.
    
        **Validates: Requirements 2.1, 2.2**
        """
        cases = {
            MonitorType.HTTP: dict(url="http://x"),
            MonitorType.PING: dict(hostname="127.0.0.1"),
            MonitorType.PORT: dict(hostname="127.0.0.1", port=8080),
            MonitorType.DNS: dict(
                hostname="example.com",
                dns_resolve_server="1.1.1.1",
                port=53,
            ),
            MonitorType.KEYWORD: dict(url="http://x", keyword="ok"),
            MonitorType.PUSH: dict(),
        }
        for type_, kwargs in cases.items():
            with self.subTest(type=type_):
                result = self._build_v1()(type=type_, name="t", **kwargs)
>               self.assertNotIn("conditions", result)
E               AssertionError: 'conditions' unexpectedly found in {'type': <MonitorType.PUSH: 'push'>, 'name': 't', 'interval': 60, 'retryInterval': 60, 'maxretries': 1, 'notificationIDList': [], 'upsideDown': False, 'resendInterval': 0, 'description': None, 'httpBodyEncoding': 'json', 'conditions': [], 'parent': None, 'url': None, 'maxredirects': 10, 'accepted_statuscodes': ['200-299'], 'expiryNotification': False, 'ignoreTls': False, 'proxyId': None, 'method': 'GET', 'body': None, 'headers': None, 'authMethod': <AuthMethod.NONE: ''>, 'timeout': 48, 'hostname': None, 'packetSize': 56, 'port': None, 'dns_resolve_server': '1.1.1.1', 'dns_resolve_type': 'A', 'mqttUsername': '', 'mqttPassword': '', 'mqttTopic': '', 'mqttSuccessMessage': '', 'databaseConnectionString': None}

tests\test_monitor_params_v2.py:1145: AssertionError
___ TestConditionsV1Gate.test_edit_monitor_explicit_conditions_raises_on_v1 ___

self = <test_monitor_params_v2.TestConditionsV1Gate testMethod=test_edit_monitor_explicit_conditions_raises_on_v1>

    def test_edit_monitor_explicit_conditions_raises_on_v1(self):
        """edit_monitor rejects an explicit conditions list before any server call.
    
        ``edit_monitor`` bypasses ``_build_monitor_data`` entirely -- it merges
        ``get_monitor(id_)`` output and calls ``editMonitor`` directly -- so it
        needs its own guard. Asserting that neither ``get_monitor`` nor
        ``_call`` was invoked is what proves the guard sits *ahead* of
        ``get_monitor(id_)``, which is requirement 2.3's "before any server call
        is made".
    
        **Validates: Requirements 2.5**
        """
        api = self._v1_api()
        api.get_monitor.return_value = {
            "id": 7,
            "type": MonitorType.HTTP,
            "name": "existing",
            "url": "http://x",
            "interval": 60,
            "maxretries": 0,
            "retryInterval": 60,
            "maxredirects": 10,
            "accepted_statuscodes": ["200-299"],
            "notificationIDList": [],
            "databaseConnectionString": None,
            # _check_arguments_monitor reads this unconditionally, so the mocked
            # server response has to carry it or the pre-fix run dies on a
            # KeyError before it can prove the guard is missing
            "dns_resolve_type": "A",
        }
        edit_monitor = UptimeKumaApi.edit_monitor.__get__(api)
    
>       with self.assertRaises(UptimeKumaException) as ctx:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: UptimeKumaException not raised

tests\test_monitor_params_v2.py:1233: AssertionError
_________ TestConditionsV1Gate.test_explicit_conditions_raises_on_v1 __________

self = <test_monitor_params_v2.TestConditionsV1Gate testMethod=test_explicit_conditions_raises_on_v1>

    def test_explicit_conditions_raises_on_v1(self):
        """An explicit conditions list on v1 raises UptimeKumaException.
    
        Silently dropping the field would produce a monitor that reports
        success against criteria the caller never set, so the field is rejected
        instead.
    
        **Validates: Requirements 2.3**
        """
        build = self._build_v1()
    
>       with self.assertRaises(UptimeKumaException) as ctx:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: UptimeKumaException not raised

tests\test_monitor_params_v2.py:1191: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_builder_conditions_raises_on_v1
FAILED tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_conditions_empty_list_omitted_on_v1
FAILED tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_conditions_omitted_on_v1
SUBFAILED(type=<MonitorType.HTTP: 'http'>) tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_conditions_omitted_on_v1_all_types
SUBFAILED(type=<MonitorType.PING: 'ping'>) tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_conditions_omitted_on_v1_all_types
SUBFAILED(type=<MonitorType.PORT: 'port'>) tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_conditions_omitted_on_v1_all_types
SUBFAILED(type=<MonitorType.DNS: 'dns'>) tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_conditions_omitted_on_v1_all_types
SUBFAILED(type=<MonitorType.KEYWORD: 'keyword'>) tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_conditions_omitted_on_v1_all_types
SUBFAILED(type=<MonitorType.PUSH: 'push'>) tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_conditions_omitted_on_v1_all_types
FAILED tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_edit_monitor_explicit_conditions_raises_on_v1
FAILED tests/test_monitor_params_v2.py::TestConditionsV1Gate::test_explicit_conditions_raises_on_v1
================= 11 failed, 1 passed, 53 deselected in 0.79s =================
```
