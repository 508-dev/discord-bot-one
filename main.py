"""
508.dev Discord Bot Entry Point

A modular Discord bot for the 508.dev co-op that allows multiple developers
to work independently on different bot functions through the cogs system.
"""

import asyncio
import logging
from bot.bot import create_bot
from bot.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point for the bot."""
    bot = create_bot()

    try:
        await bot.start(settings.discord_bot_token)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())