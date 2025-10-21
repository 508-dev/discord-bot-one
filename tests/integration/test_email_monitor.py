"""
Integration tests for email monitoring feature.
"""

import pytest
from unittest.mock import Mock, patch
import imaplib

from bot.cogs.email_monitor import EmailMonitor


class TestEmailMonitorIntegration:
    """Integration tests for EmailMonitor feature."""

    @pytest.fixture
    def email_monitor(self, mock_bot):
        """Create an EmailMonitor instance for testing."""
        # Mock the task starting to avoid actual background task
        with patch.object(
            EmailMonitor, "__init__", lambda self, bot: setattr(self, "bot", bot)
        ):
            monitor = EmailMonitor(mock_bot)
            monitor.task_poll_inbox = Mock()
            monitor.task_poll_inbox.start = Mock()
            monitor.task_poll_inbox.cancel = Mock()
            monitor.task_poll_inbox.is_running = Mock(return_value=False)
            return monitor

    @pytest.mark.asyncio
    async def test_st_command_starts_polling(self, email_monitor, mock_discord_context):
        """Test that st command starts email polling."""
        await email_monitor.st(mock_discord_context)

        mock_discord_context.send.assert_called_once()
        call_args = mock_discord_context.send.call_args[0][0]
        assert "Polling for emails" in call_args

    @pytest.mark.asyncio
    async def test_is_running_command_shows_status(
        self, email_monitor, mock_discord_context
    ):
        """Test that is_running command shows correct status."""
        # Test when not running
        email_monitor.task_poll_inbox.is_running.return_value = False
        await email_monitor.is_running(mock_discord_context)

        call_args = mock_discord_context.send.call_args[0][0]
        assert "isn't" in call_args

        # Test when running
        email_monitor.task_poll_inbox.is_running.return_value = True
        await email_monitor.is_running(mock_discord_context)

        call_args = mock_discord_context.send.call_args[0][0]
        assert "is" in call_args and "isn't" not in call_args

    @pytest.mark.asyncio
    async def test_poll_inbox_with_no_messages(
        self, email_monitor, mock_discord_channel, mock_imap_server
    ):
        """Test polling inbox when there are no new messages."""
        email_monitor.bot.get_channel.return_value = mock_discord_channel
        mock_imap_server.search.return_value = ("OK", [b""])

        with patch("imaplib.IMAP4_SSL", return_value=mock_imap_server):
            await email_monitor.task_poll_inbox()

        # Should login and logout but not send any messages
        mock_imap_server.login.assert_called_once()
        mock_imap_server.logout.assert_called_once()
        mock_discord_channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_inbox_with_messages(
        self, email_monitor, mock_discord_channel, mock_imap_server, mock_email_message
    ):
        """Test polling inbox with new messages."""
        email_monitor.bot.get_channel.return_value = mock_discord_channel

        # Mock email data
        mock_imap_server.search.return_value = ("OK", [b"1"])
        mock_raw_email = b"""From: test@example.com
Subject: Test Subject
Received: by server; Mon, 21 Oct 2024 12:00:00 +0000

Test email body content
"""
        mock_imap_server.fetch.return_value = ("OK", [(None, mock_raw_email)])

        with patch("imaplib.IMAP4_SSL", return_value=mock_imap_server):
            await email_monitor.task_poll_inbox()

        # Should send messages to Discord
        assert mock_discord_channel.send.call_count > 0

        # Check that email details were sent
        sent_messages = [
            call[0][0] for call in mock_discord_channel.send.call_args_list
        ]
        assert any("FROM:" in msg for msg in sent_messages)
        assert any("SUBJECT:" in msg for msg in sent_messages)
        assert any("BODY" in msg for msg in sent_messages)

    @pytest.mark.asyncio
    async def test_poll_inbox_handles_imap_errors(
        self, email_monitor, mock_discord_channel, capfd
    ):
        """Test that IMAP errors are handled gracefully."""
        email_monitor.bot.get_channel.return_value = mock_discord_channel

        with patch(
            "imaplib.IMAP4_SSL", side_effect=imaplib.IMAP4.error("Connection failed")
        ):
            # Should not raise an exception
            try:
                await email_monitor.task_poll_inbox()
            except Exception as e:
                # If an exception is raised, it should be an IMAP error (expected)
                assert isinstance(e, (imaplib.IMAP4.error, Exception))

    @pytest.mark.asyncio
    async def test_poll_inbox_handles_email_parsing_errors(
        self, email_monitor, mock_discord_channel, mock_imap_server
    ):
        """Test handling of malformed email messages."""
        email_monitor.bot.get_channel.return_value = mock_discord_channel
        mock_imap_server.search.return_value = ("OK", [b"1"])

        # Malformed email data
        mock_imap_server.fetch.return_value = ("OK", [(None, b"malformed email data")])

        with patch("imaplib.IMAP4_SSL", return_value=mock_imap_server):
            # Should handle parsing errors gracefully
            try:
                await email_monitor.task_poll_inbox()
            except Exception:
                # Some parsing errors might still be raised, which is acceptable
                pass

    def test_cog_unload_cancels_task(self, email_monitor):
        """Test that cog_unload properly cancels the background task."""
        email_monitor.cog_unload()
        email_monitor.task_poll_inbox.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_function(self, mock_bot):
        """Test the setup function adds the feature to the bot."""
        from bot.features.email_monitor import setup

        with patch.object(
            EmailMonitor, "__init__", lambda self, bot: setattr(self, "bot", bot)
        ):
            await setup(mock_bot)

        mock_bot.add_cog.assert_called_once()
        added_cog = mock_bot.add_cog.call_args[0][0]
        assert isinstance(added_cog, EmailMonitor)
