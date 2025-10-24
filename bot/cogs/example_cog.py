"""
Example Cog Template

This is a template for creating new bot functionality. Copy this file and modify
it to create new cogs for the 508.dev Discord bot.
"""

from discord.ext import commands
from discord import app_commands
import discord

from bot.config import settings


class ExampleCog(commands.Cog):
    """Example cog showing basic structure and common patterns."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="hello", description="Say hello and get a warm welcome!")
    async def hello_command(self, interaction: discord.Interaction) -> None:
        """Simple hello command example."""
        await interaction.response.send_message(f"Hello {interaction.user.mention}! Welcome to 508.dev!")

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping_command(self, interaction: discord.Interaction) -> None:
        """Show bot latency."""
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong! Latency: {latency}ms")

    @app_commands.command(name="info", description="Show bot and server information")
    async def info_command(self, interaction: discord.Interaction) -> None:
        """Show bot and server information."""
        embed = discord.Embed(
            title="508.dev Bot Info",
            description="A modular Discord bot for the 508.dev cooperative",
            color=0x00FF00,
        )
        if interaction.guild:
            embed.add_field(name="Server", value=interaction.guild.name, inline=True)
            embed.add_field(name="Members", value=interaction.guild.member_count, inline=True)
        embed.add_field(
            name="Bot Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True
        )

        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Example event listener - runs when a new member joins."""
        channel = self.bot.get_channel(settings.channel_id)
        if channel and isinstance(channel, discord.abc.Messageable):
            await channel.send(f"Welcome to 508.dev, {member.mention}! 🎉")


async def setup(bot: commands.Bot) -> None:
    """Required function to load the cog."""
    cog = ExampleCog(bot)
    await bot.add_cog(cog)
    # Slash commands will be synced automatically in bot.py
