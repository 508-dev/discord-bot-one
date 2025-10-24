"""
Main bot class for the 508.dev Discord bot.

This module contains the core Bot508 class that handles cog loading,
Discord events, and provides the factory function for bot creation.
"""

import logging
from pathlib import Path
from datetime import datetime
import discord
from discord.ext import commands

from bot.config import settings

logger = logging.getLogger(__name__)


class Bot508(commands.Bot):
    """
    Custom Discord bot class for 508.dev.

    This bot automatically loads all cogs from the cogs directory
    and provides enhanced functionality for the 508.dev cooperative.
    """

    def __init__(self) -> None:
        intents = discord.Intents.all()
        # Use a prefix that won't accidentally trigger since we're using slash commands
        super().__init__(command_prefix="$508$", intents=intents)
        # Remove the default help command since we're using slash commands
        self.remove_command('help')

    async def setup_hook(self) -> None:
        """Load all cogs automatically."""
        await self.load_extensions()

    async def load_extensions(self) -> None:
        """Load all cog files from the cogs directory."""
        cogs_dir = Path(__file__).parent / "cogs"
        for file in cogs_dir.glob("*.py"):
            if file.name != "__init__.py":
                cog_name = f"bot.cogs.{file.stem}"
                try:
                    await self.load_extension(cog_name)
                    logger.info(f"Loaded cog: {cog_name}")
                except Exception as e:
                    logger.error(f"Failed to load cog {cog_name}: {e}")

        # Sync slash commands after loading all cogs
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands")
            for cmd in synced:
                logger.info(f"  - /{cmd.name}: {cmd.description}")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")

    async def on_ready(self) -> None:
        """Handle bot ready event."""
        logger.info(f"Hello {self.user} ready for 508.dev!")
        channel = self.get_channel(settings.channel_id)
        if channel and isinstance(channel, discord.abc.Messageable):
            await channel.send(
                f"🤖 508.dev Bot activated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )


def create_bot() -> Bot508:
    """Factory function to create and return the bot instance."""
    return Bot508()
