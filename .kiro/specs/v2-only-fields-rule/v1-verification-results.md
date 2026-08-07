# Verification_Run results — v2-only monitor fields against Uptime Kuma 1.23.2

Requirement 7. Run before the Outcome_Rule was implemented, so the
Field_Registry is built from an observed field list rather than an assumed one.

- **Observed Server_Version:** `1.23.2`
- **Run date:** 2026-08-07
- **Target:** disposable `louislam/uptime-kuma:1.23.2` container, `kuma-v1-fields`,
  on `<docker-host>:3023` over SSH as `<user>`. Run without a volume, so removing
  it destroyed all state; removed at the end of the run.
- **Script:** `tests/live_test_v2_only_fields_v1.py`
- **Fields probed:** 25 of 26. `snmp_v3_username` is excluded because the `SNMP`
  monitor type is itself v2-only and the 2.3.1 type gate rejects it before any
  payload is built, so no caller can reach that field on a pre-2.0 server.

## Result: no field is mis-gated. The registry keeps all 26 entries.

**All 25 probed fields were `REJECTED`**, each with
`SQLITE_ERROR: table monitor has no column named <snake_case_name>`. Zero
`ACCEPTED`, zero `ABSENT`, zero `MISMATCH`, zero `NOT_OBSERVED`.

Requirement 7.2 therefore removes nothing: every gated field is genuinely
absent from the 1.x schema, so the gate is correct for all of them and the
Field_Registry is built with the full set.

## How the fields were put on the wire

They could not go through `add_monitor` — that is the code doing the gating, and
on a 1.23.x server it withholds every one of these fields before the payload is
built. The probe mirrors `add_monitor`'s own sequence and injects exactly one
field:

```python
data = api._build_monitor_data(name=name, **base)   # gated fields absent
_convert_monitor_input(data)
_check_arguments_monitor(data)
data[field] = value                                  # inject one gated field
api._call("add", data)
```

One field per monitor, deliberately. A rejected insert names a single column and
one bad column fails the whole statement, so probing several at once would
attribute one rejection to all of them.

## Verdict table

| Field | Monitor type | Verdict | Rejected column |
|---|---|---|---|
| `conditions` | HTTP | `REJECTED` | `conditions` |
| `ipFamily` | HTTP | `REJECTED` | `ip_family` |
| `cacheBust` | HTTP | `REJECTED` | `cache_bust` |
| `retryOnlyOnStatusCodeFailure` | HTTP | `REJECTED` | `retry_only_on_status_code_failure` |
| `bearer_token` | HTTP | `REJECTED` | `bearer_token` |
| `oauth_audience` | HTTP | `REJECTED` | `oauth_audience` |
| `domainExpiryNotification` | HTTP | `REJECTED` | `domain_expiry_notification` |
| `saveResponse` | HTTP | `REJECTED` | `save_response` |
| `saveErrorResponse` | HTTP | `REJECTED` | `save_error_response` |
| `responseMaxLength` | HTTP | `REJECTED` | `response_max_length` |
| `responsecheck` | HTTP | `REJECTED` | `responsecheck` |
| `subtype` | HTTP | `REJECTED` | `subtype` |
| `wsSubprotocol` | HTTP | `REJECTED` | `ws_subprotocol` |
| `wsIgnoreSecWebsocketAcceptHeader` | HTTP | `REJECTED` | `ws_ignore_sec_websocket_accept_header` |
| `remoteBrowsersToggle` | HTTP | `REJECTED` | `remote_browsers_toggle` |
| `remote_browser` | HTTP | `REJECTED` | `remote_browser` |
| `screenshot_delay` | HTTP | `REJECTED` | `screenshot_delay` |
| `gamedigToken` | HTTP | `REJECTED` | `gamedig_token` |
| `protocol` | HTTP | `REJECTED` | `protocol` |
| `jsonPathOperator` | JSON_QUERY | `REJECTED` | `json_path_operator` |
| `ping_count` | PING | `REJECTED` | `ping_count` |
| `ping_numeric` | PING | `REJECTED` | `ping_numeric` |
| `ping_per_request_timeout` | PING | `REJECTED` | `ping_per_request_timeout` |
| `mqttWebsocketPath` | MQTT | `REJECTED` | `mqtt_websocket_path` |
| `mqttCheckType` | MQTT | `REJECTED` | `mqtt_check_type` |
| `snmp_v3_username` | SNMP | not probed | unreachable behind the 2.3.1 type gate |

No monitor was created during the run — all 25 inserts were rejected — so
cleanup had nothing to delete. That is itself a confirmation: had any field been
accepted, a monitor would exist and appear in the deletion count.

## What this settles, and what it does not

**Settles:** the "unverified" objection that shaped the ratified policy. The
`conditions-field-v1-regression` design declined to raise for the adjacent
fields partly because "whether each actually fails on v1 is **unverified**, so
raising would convert a possibly-working path into a guaranteed hard error".
That unknown is now closed in the direction that removes the ambiguity: there is
no possibly-working path for any of the 25. Each one fails at the database layer.

**Does not change decision 1.** Withhold-plus-Signal remains correct, and this
run arguably strengthens it. A caller who supplies one of these fields against a
1.x server today gets a *working monitor*, because the library withholds the
field before the payload is built. Raising would take that working call away.
Since the field can never reach a 1.x server successfully under any client-side
choice, withholding is the only behaviour that lets the call succeed at all —
and a warning is exactly the right way to say so.

One nuance worth recording rather than leaving to be re-derived: the failure mode
observed here is the *ungated* one. It is what a caller would see if the gate
were removed, not what they see today. Today they see success with the field
missing and no notification, which is the gap this feature closes.

## Ansible collection stderr check (requirement 7.11)

`warnings.warn` writes to stderr through `warnings.showwarning`, and the
companion Ansible collection wraps these library calls in a module process.

**Finding:** an Ansible module's contract is that its **stdout** must be a single
JSON document; stderr is captured separately and surfaced in the task result
rather than parsed. Writing to stderr therefore does not corrupt module output.
The practical consequence is cosmetic — warning text can appear in verbose task
output — and it is suppressible by the playbook author, since the category is
exported and filterable.

**Decision: keep `warnings.warn`.** The `logging` fallback is not taken. Recorded
here so a later reader does not have to re-establish it, along with the reason the
fallback would have cost something: `UptimeKumaApi.__init__` already imports
`logging` to type-check the caller-supplied `logger` it forwards to
`socketio.Client`, so routing the Signal through `logging` would leave two
unrelated logger concepts in one class — the caller's, for socketio's output, and
the library's own.
