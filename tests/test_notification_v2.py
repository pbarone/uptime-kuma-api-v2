import unittest

from uptime_kuma_api import NotificationType
from uptime_kuma_api.api import _build_notification_data, _check_arguments_notification


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


if __name__ == "__main__":
    unittest.main()
