"""
Unit tests for bot configuration.
"""

import pytest
from pydantic import ValidationError

from bot.config import Settings


class TestSettings:
    """Test the Settings configuration class."""

    def test_settings_with_all_required_fields(self, monkeypatch):
        """Test settings creation with all required fields."""
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token")
        monkeypatch.setenv("EMAIL_USERNAME", "test@example.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "test_password")

        settings = Settings()

        assert settings.discord_bot_token == "test_token"
        assert settings.email_username == "test@example.com"
        assert settings.email_password == "test_password"

    def test_settings_default_values(self, monkeypatch):
        """Test that default values are properly set."""
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token")
        monkeypatch.setenv("EMAIL_USERNAME", "test@example.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "test_password")

        settings = Settings()

        assert settings.channel_id == 1391742724666822798
        assert settings.max_session_time_minutes == 2
        assert settings.check_email_wait == 2
        assert settings.imap_server == "imap.migadu.com"
        assert settings.smtp_server == "smtp.migadu.com"
        assert settings.discord_sendmsg_character_limit == 2000

    def test_settings_custom_values(self, monkeypatch):
        """Test settings with custom environment variables."""
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "custom_token")
        monkeypatch.setenv("EMAIL_USERNAME", "custom@example.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "custom_password")
        monkeypatch.setenv("CHANNEL_ID", "999888777")
        monkeypatch.setenv("CHECK_EMAIL_WAIT", "5")
        monkeypatch.setenv("IMAP_SERVER", "custom.imap.com")

        settings = Settings()

        assert settings.discord_bot_token == "custom_token"
        assert settings.email_username == "custom@example.com"
        assert settings.email_password == "custom_password"
        assert settings.channel_id == 999888777
        assert settings.check_email_wait == 5
        assert settings.imap_server == "custom.imap.com"

    def test_settings_missing_required_field(self, monkeypatch):
        """Test that missing required fields raise ValidationError."""
        monkeypatch.setenv("EMAIL_USERNAME", "test@example.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "test_password")
        # Missing DISCORD_BOT_TOKEN

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "discord_bot_token" in str(exc_info.value)

    def test_settings_invalid_type(self, monkeypatch):
        """Test that invalid types raise ValidationError."""
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token")
        monkeypatch.setenv("EMAIL_USERNAME", "test@example.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "test_password")
        monkeypatch.setenv("CHANNEL_ID", "not_a_number")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "channel_id" in str(exc_info.value)

    def test_settings_env_file_loading(self, tmp_path, monkeypatch):
        """Test that .env file is loaded correctly."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "DISCORD_BOT_TOKEN=env_file_token\n"
            "EMAIL_USERNAME=env@example.com\n"
            "EMAIL_PASSWORD=env_password\n"
        )

        # Change to the temp directory so .env is found
        monkeypatch.chdir(tmp_path)

        settings = Settings()

        assert settings.discord_bot_token == "env_file_token"
        assert settings.email_username == "env@example.com"
        assert settings.email_password == "env_password"

    def test_settings_type_validation(self, monkeypatch):
        """Test that settings have correct types."""
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token")
        monkeypatch.setenv("EMAIL_USERNAME", "test@example.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "test_password")

        settings = Settings()

        assert isinstance(settings.discord_bot_token, str)
        assert isinstance(settings.channel_id, int)
        assert isinstance(settings.max_session_time_minutes, int)
        assert isinstance(settings.check_email_wait, int)
        assert isinstance(settings.email_username, str)
        assert isinstance(settings.email_password, str)
        assert isinstance(settings.imap_server, str)
        assert isinstance(settings.smtp_server, str)
        assert isinstance(settings.discord_sendmsg_character_limit, int)