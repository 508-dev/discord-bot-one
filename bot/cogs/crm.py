"""
CRM integration cog for the 508.dev Discord bot.

This cog provides commands for interacting with EspoCRM through Discord slash commands.
It allows team members to quickly access CRM data without leaving Discord.
"""

import logging
from typing import Optional, List
from discord.ext import commands
from discord import app_commands
import discord

from bot.config import settings
from bot.utils.espo_api_client import EspoAPI, EspoAPIError

logger = logging.getLogger(__name__)


class CRMCog(commands.Cog):
    """CRM integration cog for EspoCRM operations."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.espo_api = EspoAPI(settings.espo_api_url, settings.espo_api_key)

    @app_commands.command(name="crm-contacts", description="Search for contacts in the CRM")
    @app_commands.describe(query="Search term (name, Discord username, email, or 508 email)")
    async def search_contacts(self, interaction: discord.Interaction, query: str) -> None:
        """Search for contacts in the CRM."""
        try:
            await interaction.response.defer(ephemeral=True)

            # Search contacts using EspoCRM API
            search_params = {
                'where': [
                    {
                        'type': 'or',
                        'value': [
                            {
                                'type': 'contains',
                                'attribute': 'name',
                                'value': query
                            },
                            {
                                'type': 'contains',
                                'attribute': 'cDiscordUsername',
                                'value': query
                            },
                            {
                                'type': 'contains',
                                'attribute': 'emailAddress',
                                'value': query
                            },
                            {
                                'type': 'contains',
                                'attribute': 'c508Email',
                                'value': query
                            }
                        ]
                    }
                ],
                'maxSize': 5,
                'select': ['id', 'name', 'emailAddress', 'c508Email', 'cDiscordUsername', 'phoneNumber', 'type']
            }

            response = self.espo_api.request('GET', 'Contact', search_params)
            contacts = response.get('list', [])

            if not contacts:
                await interaction.followup.send(f"🔍 No contacts found for: `{query}`")
                return

            # Create embed with results
            embed = discord.Embed(
                title="🔍 CRM Contact Search Results",
                description=f"Found {len(contacts)} contact(s) for: `{query}`",
                color=0x0099ff
            )

            for contact in contacts:
                name = contact.get('name', 'Unknown')
                email = contact.get('emailAddress', 'No email')
                contact_type = contact.get('type', 'Unknown')
                email_508 = contact.get('c508Email', 'None')
                discord_username = contact.get('cDiscordUsername', 'No Discord')

                contact_info = f"📧 {email}\n🏷️ Type: {contact_type}"

                # Only show 508 email and Discord for Candidates/Members
                if contact_type in ['Candidate / Member', 'Member']:
                    contact_info += f"\n🏢 508 Email: {email_508}\n💬 Discord: {discord_username}"

                embed.add_field(
                    name=f"👤 {name}",
                    value=contact_info,
                    inline=True
                )

            await interaction.followup.send(embed=embed)

        except EspoAPIError as e:
            logger.error(f"EspoCRM API error: {e}")
            await interaction.followup.send(f"❌ CRM API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in CRM search: {e}")
            await interaction.followup.send("❌ An unexpected error occurred while searching the CRM.")

    @app_commands.command(name="crm-status", description="Check CRM API connection status")
    async def crm_status(self, interaction: discord.Interaction) -> None:
        """Check if the CRM API is accessible."""
        try:
            await interaction.response.defer(ephemeral=True)

            # Try a simple API call to check connectivity
            response = self.espo_api.request('GET', 'App/user')
            user_name = response.get('user', {}).get('name', 'Unknown')

            embed = discord.Embed(
                title="✅ CRM Status",
                description="Connection to EspoCRM is working!",
                color=0x00ff00
            )
            embed.add_field(name="Connected as", value=user_name, inline=True)
            embed.add_field(name="API URL", value=settings.espo_api_url, inline=True)

            await interaction.followup.send(embed=embed)

        except EspoAPIError as e:
            logger.error(f"EspoCRM API error: {e}")
            embed = discord.Embed(
                title="❌ CRM Status",
                description=f"Failed to connect to EspoCRM: {str(e)}",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Unexpected error in CRM status: {e}")
            embed = discord.Embed(
                title="❌ CRM Status",
                description="An unexpected error occurred while checking CRM status.",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Add the CRM cog to the bot."""
    cog = CRMCog(bot)
    await bot.add_cog(cog)
    # Slash commands will be synced automatically in bot.py