"""
Example Cog Template

This is a template for creating new bot functionality. Copy this file and modify
it to create new cogs for the 508.dev Discord bot.
"""

from discord.ext import commands
import discord

from bot.config import settings


class ExampleCog(commands.Cog):
    """Example cog showing basic structure and common patterns."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="hello")
    async def hello_command(self, ctx: commands.Context) -> None:
        """Simple hello command example."""
        await ctx.send(f"Hello {ctx.author.mention}! Welcome to 508.dev!")

    @commands.command(name="ping")
    async def ping_command(self, ctx: commands.Context) -> None:
        """Show bot latency."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"🏓 Pong! Latency: {latency}ms")

    @commands.command(name="info")
    async def info_command(self, ctx: commands.Context) -> None:
        """Show bot and server information."""
        embed = discord.Embed(
            title="508.dev Bot Info",
            description="A modular Discord bot for the 508.dev cooperative",
            color=0x00FF00,
        )
        if ctx.guild:
            embed.add_field(name="Server", value=ctx.guild.name, inline=True)
            embed.add_field(name="Members", value=ctx.guild.member_count, inline=True)
        embed.add_field(
            name="Bot Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True
        )

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Example event listener - runs when a new member joins."""
        channel = self.bot.get_channel(settings.channel_id)
        if channel and isinstance(channel, discord.abc.Messageable):
            await channel.send(f"Welcome to 508.dev, {member.mention}! 🎉")


async def setup(bot: commands.Bot) -> None:
    """Required function to load the cog."""
    await bot.add_cog(ExampleCog(bot))
