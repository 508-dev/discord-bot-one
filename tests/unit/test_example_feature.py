"""
Unit tests for the example cog.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from bot.cogs.example_cog import ExampleCog


class TestExampleCog:
    """Test the ExampleCog class."""

    @pytest.fixture
    def cog(self, mock_bot):
        """Create an ExampleCog instance for testing."""
        return ExampleCog(mock_bot)

    @pytest.mark.asyncio
    async def test_hello_command(self, cog, mock_discord_context):
        """Test the hello command responds correctly."""
        await cog.hello_command(mock_discord_context)

        mock_discord_context.send.assert_called_once()
        call_args = mock_discord_context.send.call_args[0][0]
        assert "Hello" in call_args
        assert mock_discord_context.author.mention in call_args
        assert "508.dev" in call_args

    @pytest.mark.asyncio
    async def test_ping_command(self, cog, mock_discord_context):
        """Test the ping command shows latency."""
        cog.bot.latency = 0.123

        await cog.ping_command(mock_discord_context)

        mock_discord_context.send.assert_called_once()
        call_args = mock_discord_context.send.call_args[0][0]
        assert "Pong!" in call_args
        assert "123ms" in call_args  # 0.123 * 1000 = 123ms

    @pytest.mark.asyncio
    async def test_info_command(self, cog, mock_discord_context):
        """Test the info command creates and sends an embed."""
        await cog.info_command(mock_discord_context)

        mock_discord_context.send.assert_called_once()
        # Check that an embed was passed
        call_kwargs = mock_discord_context.send.call_args[1]
        assert "embed" in call_kwargs

    @pytest.mark.asyncio
    async def test_on_member_join_sends_welcome(self, cog, mock_discord_member, mock_discord_channel):
        """Test that on_member_join sends welcome message."""
        cog.bot.get_channel.return_value = mock_discord_channel

        await cog.on_member_join(mock_discord_member)

        mock_discord_channel.send.assert_called_once()
        call_args = mock_discord_channel.send.call_args[0][0]
        assert "Welcome to 508.dev" in call_args
        assert mock_discord_member.mention in call_args

    @pytest.mark.asyncio
    async def test_on_member_join_handles_no_channel(self, cog, mock_discord_member):
        """Test that on_member_join handles missing channel gracefully."""
        cog.bot.get_channel.return_value = None

        # Should not raise an exception
        await cog.on_member_join(mock_discord_member)

    @pytest.mark.asyncio
    async def test_setup_function(self, mock_bot):
        """Test the setup function adds the cog to the bot."""
        from bot.cogs.example_cog import setup

        await setup(mock_bot)

        mock_bot.add_cog.assert_called_once()
        # Check that an ExampleFeature instance was added
        added_cog = mock_bot.add_cog.call_args[0][0]
        assert isinstance(added_cog, ExampleFeature)