import doctest
import pathlib
import re
import textwrap
import unittest
from unittest.mock import MagicMock, patch

import uptime_kuma_api
from uptime_kuma_api import MonitorType, NotificationType, UptimeKumaApi
from uptime_kuma_api.api import (
    _build_notification_data,
    _check_arguments_notification,
    _convert_monitor_input,
    _convert_monitor_return,
)
from uptime_kuma_api.notification_providers import (
    notification_provider_conditions,
    notification_provider_options,
)


class TestNotificationProvidersV2(unittest.TestCase):
    """Unit tests for new v2 notification providers: Nextcloud Talk, Brevo, Evolution API."""

    # ─── Nextcloud Talk ───────────────────────────────────────────────────

    def test_nextcloud_talk_valid(self):
        """Nextcloud Talk: valid with all required fields → no error, correct dict."""
        data = _build_notification_data(
            name="test",
            type=NotificationType.NEXTCLOUD_TALK,
            host="https://nextcloud.example.com",
            conversationToken="abc123",
            botSecret="secret123",
        )
        assert data["type"] == NotificationType.NEXTCLOUD_TALK
        assert data["name"] == "test"
        assert data["host"] == "https://nextcloud.example.com"
        assert data["conversationToken"] == "abc123"
        assert data["botSecret"] == "secret123"
        # _check_arguments_notification should not raise
        _check_arguments_notification(data)

    def test_nextcloud_talk_missing_bot_secret(self):
        """Nextcloud Talk: missing botSecret → _check_arguments_notification raises TypeError."""
        data = _build_notification_data(
            name="test",
            type=NotificationType.NEXTCLOUD_TALK,
            host="https://nextcloud.example.com",
            conversationToken="abc123",
        )
        with self.assertRaises(TypeError):
            _check_arguments_notification(data)

    def test_nextcloud_talk_with_optional_fields(self):
        """Nextcloud Talk: optional fields included in output."""
        data = _build_notification_data(
            name="test",
            type=NotificationType.NEXTCLOUD_TALK,
            host="https://nextcloud.example.com",
            conversationToken="abc123",
            botSecret="secret123",
            sendSilentUp=True,
            sendSilentDown=False,
        )
        assert data["sendSilentUp"] is True
        assert data["sendSilentDown"] is False
        # Should still validate cleanly
        _check_arguments_notification(data)

    # ─── Brevo ────────────────────────────────────────────────────────────

    def test_brevo_valid(self):
        """Brevo: valid with all required fields → no error, correct dict."""
        data = _build_notification_data(
            name="test",
            type=NotificationType.BREVO,
            brevoApiKey="xkeysib-abc123",
            brevoFromEmail="sender@example.com",
            brevoToEmail="recipient@example.com",
        )
        assert data["type"] == NotificationType.BREVO
        assert data["name"] == "test"
        assert data["brevoApiKey"] == "xkeysib-abc123"
        assert data["brevoFromEmail"] == "sender@example.com"
        assert data["brevoToEmail"] == "recipient@example.com"
        # _check_arguments_notification should not raise
        _check_arguments_notification(data)

    def test_brevo_missing_api_key(self):
        """Brevo: missing brevoApiKey → raises TypeError."""
        data = _build_notification_data(
            name="test",
            type=NotificationType.BREVO,
            brevoFromEmail="sender@example.com",
            brevoToEmail="recipient@example.com",
        )
        with self.assertRaises(TypeError):
            _check_arguments_notification(data)

    def test_brevo_with_optional_fields(self):
        """Brevo: optional fields included in output."""
        data = _build_notification_data(
            name="test",
            type=NotificationType.BREVO,
            brevoApiKey="xkeysib-abc123",
            brevoFromEmail="sender@example.com",
            brevoToEmail="recipient@example.com",
            brevoFromName="My Service",
            brevoCcEmail="cc@example.com",
            brevoBccEmail="bcc@example.com",
            brevoSubject="Alert: Monitor Down",
        )
        assert data["brevoFromName"] == "My Service"
        assert data["brevoCcEmail"] == "cc@example.com"
        assert data["brevoBccEmail"] == "bcc@example.com"
        assert data["brevoSubject"] == "Alert: Monitor Down"
        # Should still validate cleanly
        _check_arguments_notification(data)

    # ─── Evolution API ────────────────────────────────────────────────────

    def test_evolution_api_valid(self):
        """Evolution API: valid with all required fields → no error, correct dict."""
        data = _build_notification_data(
            name="test",
            type=NotificationType.EVOLUTION_API,
            evolutionInstanceName="my-instance",
            evolutionAuthToken="token123",
            evolutionRecipient="5511999999999",
        )
        assert data["type"] == NotificationType.EVOLUTION_API
        assert data["name"] == "test"
        assert data["evolutionInstanceName"] == "my-instance"
        assert data["evolutionAuthToken"] == "token123"
        assert data["evolutionRecipient"] == "5511999999999"
        # _check_arguments_notification should not raise
        _check_arguments_notification(data)

    def test_evolution_api_missing_recipient(self):
        """Evolution API: missing evolutionRecipient → raises TypeError."""
        data = _build_notification_data(
            name="test",
            type=NotificationType.EVOLUTION_API,
            evolutionInstanceName="my-instance",
            evolutionAuthToken="token123",
        )
        with self.assertRaises(TypeError):
            _check_arguments_notification(data)

    def test_evolution_api_with_optional_fields(self):
        """Evolution API: optional fields included in output."""
        data = _build_notification_data(
            name="test",
            type=NotificationType.EVOLUTION_API,
            evolutionInstanceName="my-instance",
            evolutionAuthToken="token123",
            evolutionRecipient="5511999999999",
            evolutionApiUrl="https://api.evolution.example.com",
            evolutionUseCustomMessage=True,
            evolutionCustomMessage="Monitor {{NAME}} is {{STATUS}}",
        )
        assert data["evolutionApiUrl"] == "https://api.evolution.example.com"
        assert data["evolutionUseCustomMessage"] is True
        assert data["evolutionCustomMessage"] == "Monitor {{NAME}} is {{STATUS}}"
        # Should still validate cleanly
        _check_arguments_notification(data)


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Canonical auth-note phrase for #60/#73. The haystack and the needle are both
# lowercased and stripped of quote/backtick characters before matching, so any
# quoting style around "API key" is accepted, but the wording must match.
AUTH_NOTE_PHRASE = 'UI "API key" cannot authenticate this socket.io API'
AUTH_NOTE_METRICS_HINT = "/metrics"


def _normalise(text: str) -> str:
    """Lowercase, collapse whitespace and drop quote/backtick chars."""
    if not text:
        return ""
    text = re.sub(r"[\"'`]", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _class_docstring() -> str:
    return UptimeKumaApi.__doc__ or ""


def _docstring_doctest_source() -> str:
    """The ``>>>`` example lines of the UptimeKumaApi class docstring."""
    examples = doctest.DocTestParser().get_examples(_class_docstring())
    return "".join(example.source for example in examples)


def _docstring_codeblock_source() -> str:
    """The ``.. code-block:: python`` context-manager example source."""
    match = re.search(
        r"\.\. code-block:: python\n(.*?)(?:\n\s*:param|\Z)",
        _class_docstring(),
        re.S,
    )
    if not match:
        raise AssertionError("no '.. code-block:: python' example in the class docstring")
    return textwrap.dedent(match.group(1)).strip("\n")


def _exec_example(source: str) -> None:
    """
    Execute a documentation example in a fresh namespace.

    ``uptime_kuma_api.UptimeKumaApi`` is replaced by a MagicMock so the example's
    own ``from uptime_kuma_api import UptimeKumaApi`` line resolves to a stub and
    no network connection is made. Every other name in the example must be
    resolved by the example's own imports, so a missing import raises NameError.
    """
    with patch.object(uptime_kuma_api, "UptimeKumaApi", MagicMock()):
        exec(compile(source, "<docstring-example>", "exec"), {})


class TestBugFDocsAndMetadata(unittest.TestCase):
    """
    Bug F bug-condition exploration tests (#78, #80, #60/#73, #69, #57).

    Property 11: Bug Condition - Examples run and metadata types are correct.

    isBugCondition_F(X) = exampleFailsToRun(X) OR metadataTypeIncorrect(X)

    These tests are EXPECTED TO FAIL against the unfixed code; each failure is
    the counterexample proving the defect exists. They become the fix
    verification once tasks 19.1-19.3 land.
    """

    # ─── Metadata: #69 SMTP smtpSecure declared type ───────────────────────

    def test_smtp_smtp_secure_declared_type_is_bool(self):
        """
        SMTP provider metadata declares smtpSecure as a boolean (#69).

        Upstream ``SMTP.vue`` treats smtpSecure as a boolean, so the declared
        type consumed by the required-arg check, the generated docstrings and
        the downstream Ansible collection must say so.

        **Validates: Requirements 1.12, 2.13**
        """
        smtp_options = notification_provider_options[NotificationType.SMTP]
        self.assertIn("smtpSecure", smtp_options)
        self.assertEqual(smtp_options["smtpSecure"]["type"], "bool")

    # ─── Metadata: #57 notificationIDList declared default ─────────────────

    def test_notification_id_list_declared_default_is_list(self):
        """
        The declared notificationIDList default is a list, not a dict (#57).

        ``_build_monitor_data`` declares ``notificationIDList: list = None`` and
        normalises the unset value; that normalised default must match the
        declared list type. This is a declared-type correction only - the
        runtime ``{id: True}`` conversion in ``_convert_monitor_input`` is out of
        scope here (covered by the task 18 preservation test).

        **Validates: Requirements 1.13, 2.14**
        """
        api = MagicMock(spec=UptimeKumaApi)
        api.version = "2.4.0"
        api._parsed_version = UptimeKumaApi._parsed_version.__get__(api)
        build = UptimeKumaApi._build_monitor_data.__get__(api)

        data = build(type=MonitorType.HTTP, name="test", url="http://example.com")

        self.assertIsInstance(data["notificationIDList"], list)
        self.assertEqual(data["notificationIDList"], [])

    # ─── Docs: #78 MonitorType import missing from the examples ───────────

    def test_class_docstring_doctest_example_runs(self):
        """
        The class docstring ``>>>`` example runs without NameError (#78).

        The example references ``MonitorType.HTTP`` but the shown import line
        only imports ``UptimeKumaApi``, so copy-pasting it fails.

        **Validates: Requirements 1.9, 2.10**
        """
        source = _docstring_doctest_source()
        self.assertIn("MonitorType", source, "example no longer exercises MonitorType")
        try:
            _exec_example(source)
        except NameError as e:
            self.fail(f"class docstring example raised NameError: {e}")

    def test_class_docstring_context_manager_example_runs(self):
        """
        The class docstring context-manager example runs without NameError (#78).

        **Validates: Requirements 1.9, 2.10**
        """
        source = _docstring_codeblock_source()
        self.assertIn("MonitorType", source, "example no longer exercises MonitorType")
        try:
            _exec_example(source)
        except NameError as e:
            self.fail(f"class docstring context-manager example raised NameError: {e}")

    # ─── Docs: #80 add_monitor return-key casing ───────────────────────────

    def test_class_docstring_shows_monitorid_return_key(self):
        """
        The documented add_monitor return key is ``monitorID`` (#80).

        The real server return key is ``monitorID``; the class docstring example
        shows ``monitorId``, so a reader who copies it hits a KeyError.

        **Validates: Requirements 1.10, 2.11**
        """
        doc = _class_docstring()
        self.assertIn("'monitorID'", doc)
        self.assertNotIn("'monitorId'", doc)

    # ─── Docs: #60/#73 auth note ───────────────────────────────────────────

    def test_auth_note_states_ui_api_key_cannot_authenticate(self):
        """
        The docs state the UI "API key" cannot authenticate this API (#60/#73).

        Uptime Kuma UI API keys are ``/metrics``-only, so they cannot be used to
        authenticate this socket.io API. The note may live in the
        ``UptimeKumaApi`` class docstring, the ``login`` docstring or README.

        **Validates: Requirements 1.11, 2.12**
        """
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        haystacks = {
            "UptimeKumaApi class docstring": _class_docstring(),
            "login docstring": UptimeKumaApi.login.__doc__ or "",
            "login_by_token docstring": UptimeKumaApi.login_by_token.__doc__ or "",
            "README.md": readme,
        }
        needle = _normalise(AUTH_NOTE_PHRASE)

        matches = [
            where for where, text in haystacks.items() if needle in _normalise(text)
        ]
        self.assertTrue(
            matches,
            f"auth note {AUTH_NOTE_PHRASE!r} not found in any of: "
            f"{', '.join(haystacks)}",
        )
        for where in matches:
            self.assertIn(
                AUTH_NOTE_METRICS_HINT,
                haystacks[where],
                f"auth note in {where} does not mention {AUTH_NOTE_METRICS_HINT}",
            )


class TestBugFPreservation(unittest.TestCase):
    """
    Bug F preservation tests (#57, #69).

    Property 12: Preservation - Runtime behaviour and shapes unchanged.

    For every input where ``isBugCondition_F`` does NOT hold (i.e. any runtime
    call), ``runtimeBehavior(F'(X)) = runtimeBehavior(F(X))``. The docs/metadata
    sweep of tasks 19.1-19.3 is behaviour-neutral, so these tests encode the
    UNFIXED runtime baseline and MUST stay green across the fix.

    Baseline observed against the unfixed tree:

    - ``_build_monitor_data`` declared default for ``notificationIDList``: ``{}``
      (task 19.3 changes it to ``[]``; both are falsy)
    - effective payload after ``_convert_monitor_input`` when unset: ``{}``
    - effective payload for ``[1, 2]``: ``{1: True, 2: True}``
    - ``_convert_monitor_return({"1": True, "2": True})`` -> ``[1, 2]``
    - every ``smtpSecure`` value is accepted and forwarded verbatim; it is not
      a required arg and has no declared condition, so the declared type is not
      consumed by validation

    **Validates: Requirements 3.9, 3.10, 3.11**
    """

    # ─── #57: effective notificationIDList payload ─────────────────────────

    @staticmethod
    def _build_monitor(**kwargs) -> dict:
        """Build monitor data with a mocked api instance (no server needed)."""
        api = MagicMock(spec=UptimeKumaApi)
        api.version = "2.4.0"
        api._parsed_version = UptimeKumaApi._parsed_version.__get__(api)
        build = UptimeKumaApi._build_monitor_data.__get__(api)
        return build(**kwargs)

    def test_effective_payload_for_unset_notifications_is_empty_dict(self):
        """
        An unset ``notificationIDList`` still emits ``{}`` to the server (#57).

        This is the payload ``add_monitor``/``edit_monitor`` actually send: the
        declared default is normalised by ``_convert_monitor_input`` into the
        ``{id: True}`` map shape the server expects, which for "no
        notifications" is the empty dict. The ``{}``->``[]`` declared-type
        correction must not change this.

        **Validates: Requirements 3.10**
        """
        data = self._build_monitor(
            type=MonitorType.HTTP, name="test", url="http://example.com"
        )
        _convert_monitor_input(data)

        self.assertIsInstance(data["notificationIDList"], dict)
        self.assertEqual(data["notificationIDList"], {})

    def test_effective_payload_for_populated_list_is_true_map(self):
        """
        A populated ``notificationIDList`` still becomes a ``{id: True}`` map.

        **Validates: Requirements 3.10**
        """
        data = self._build_monitor(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            notificationIDList=[1, 2],
        )
        _convert_monitor_input(data)

        self.assertEqual(data["notificationIDList"], {1: True, 2: True})

    def test_declared_default_dict_and_list_produce_identical_payload(self):
        """
        ``{}`` and ``[]`` declared defaults yield the same effective payload.

        This is the crux of why #57 is declared-type only: both are falsy, so
        ``_convert_monitor_input``'s ``if kwargs["notificationIDList"]:`` branch
        is skipped either way and the emitted payload is ``{}``. Encoding both
        the pre-fix and post-fix declared default here proves the runtime
        conversion is unaffected by task 19.3.

        **Validates: Requirements 3.10**
        """
        payloads = []
        for declared_default in ({}, [], None):
            with self.subTest(declared_default=declared_default):
                data = self._build_monitor(
                    type=MonitorType.HTTP, name="test", url="http://example.com"
                )
                data["notificationIDList"] = declared_default
                _convert_monitor_input(data)
                self.assertEqual(data["notificationIDList"], {})
                payloads.append(data["notificationIDList"])

        self.assertEqual(payloads[0], payloads[1])
        self.assertEqual(payloads[1], payloads[2])

    def test_convert_monitor_input_leaves_other_keys_untouched(self):
        """
        Only ``notificationIDList`` is rewritten; the payload shape is stable.

        Guards Requirement 3.9 (same return shapes) at the conversion site: the
        key set is unchanged and no sibling value is mutated by the conversion.

        **Validates: Requirements 3.9**
        """
        data = self._build_monitor(
            type=MonitorType.HTTP,
            name="test",
            url="http://example.com",
            notificationIDList=[1],
        )
        before = {k: v for k, v in data.items() if k != "notificationIDList"}

        self.assertIsNone(_convert_monitor_input(data), "conversion mutates in place")

        after = {k: v for k, v in data.items() if k != "notificationIDList"}
        self.assertEqual(sorted(before), sorted(after))
        self.assertEqual(before, after)

    def test_convert_monitor_return_round_trips_true_map_to_int_list(self):
        """
        The server's ``{id: True}`` map still converts back to a list of ints.

        Completes the round trip: ``[1, 2]`` -> ``{1: True, 2: True}`` on input,
        ``{"1": True, "2": True}`` -> ``[1, 2]`` on return. The public return
        shape for ``notificationIDList`` is a list of ints.

        **Validates: Requirements 3.9, 3.10**
        """
        monitor = {"notificationIDList": {"1": True, "2": True}}
        _convert_monitor_return(monitor)
        self.assertEqual(monitor["notificationIDList"], [1, 2])

        # An already-converted list is passed through unchanged.
        monitor = {"notificationIDList": [1, 2]}
        _convert_monitor_return(monitor)
        self.assertEqual(monitor["notificationIDList"], [1, 2])

    # ─── #69: accepted smtpSecure values ───────────────────────────────────

    SMTP_REQUIRED_BASE = dict(
        smtpHost="smtp.example.com",
        smtpPort=25,
        smtpFrom="sender@example.com",
    )

    SMTP_SECURE_VALUES = (True, False, None, "", "nofc", "secure", 0, 1)

    def test_accepted_smtp_secure_values_unchanged(self):
        """
        Every ``smtpSecure`` value is still accepted and forwarded verbatim (#69).

        ``str``->``bool`` in the provider table changes the declared type used by
        the docs/Ansible consumers, not what ``_build_notification_data`` +
        ``_check_arguments_notification`` accept: validation only checks required
        args and declared conditions, and ``smtpSecure`` is neither required nor
        conditioned. The value reaches the server exactly as supplied.

        **Validates: Requirements 3.11**
        """
        for value in self.SMTP_SECURE_VALUES:
            with self.subTest(smtpSecure=value):
                data = _build_notification_data(
                    name="test",
                    type=NotificationType.SMTP,
                    smtpSecure=value,
                    **self.SMTP_REQUIRED_BASE,
                )
                _check_arguments_notification(data)
                self.assertEqual(data["smtpSecure"], value)
                self.assertIs(type(data["smtpSecure"]), type(value))

    def test_smtp_secure_remains_optional(self):
        """
        Omitting ``smtpSecure`` still validates, and it stays a non-required arg.

        The metadata correction must not promote ``smtpSecure`` to required nor
        add a condition that would reject a previously accepted value.

        **Validates: Requirements 3.11**
        """
        smtp_options = notification_provider_options[NotificationType.SMTP]
        self.assertFalse(smtp_options["smtpSecure"]["required"])
        self.assertNotIn("smtpSecure", notification_provider_conditions)

        data = _build_notification_data(
            name="test", type=NotificationType.SMTP, **self.SMTP_REQUIRED_BASE
        )
        _check_arguments_notification(data)
        self.assertNotIn("smtpSecure", data)

    def test_smtp_required_argument_set_unchanged(self):
        """
        The SMTP required-arg set is unchanged by the declared-type correction.

        **Validates: Requirements 3.9, 3.11**
        """
        smtp_options = notification_provider_options[NotificationType.SMTP]
        required = sorted(k for k, v in smtp_options.items() if v["required"])
        self.assertEqual(required, ["smtpFrom", "smtpHost", "smtpPort"])


if __name__ == "__main__":
    unittest.main()
