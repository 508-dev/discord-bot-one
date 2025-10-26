"""
CRM integration cog for the 508.dev Discord bot.

This cog provides commands for interacting with EspoCRM through Discord slash commands.
It allows team members to quickly access CRM data without leaving Discord.
"""

import logging
import io
from discord.ext import commands
from discord import app_commands
import discord

from bot.config import settings
from bot.utils.espo_api_client import EspoAPI, EspoAPIError
from bot.utils.role_decorators import require_role, check_user_roles_with_hierarchy

logger = logging.getLogger(__name__)


class ResumeButtonView(discord.ui.View):
    """View containing resume download buttons for contact search results."""

    def __init__(self) -> None:
        super().__init__(timeout=300)  # 5 minute timeout

    def add_resume_button(self, contact_name: str, resume_id: str) -> None:
        """Add a resume download button for a contact."""
        if len(self.children) >= 5:  # Discord limit of 5 buttons per row
            return

        button = ResumeDownloadButton(contact_name, resume_id)
        self.add_item(button)


class ResumeDownloadButton(discord.ui.Button[discord.ui.View]):
    """Button for downloading a specific contact's resume."""

    def __init__(self, contact_name: str, resume_id: str) -> None:
        self.contact_name = contact_name
        self.resume_id = resume_id

        # Truncate long names for button label
        label = f"📄 Resume: {contact_name}"
        if len(label) > 80:  # Discord button label limit
            # Account for "📄 Resume: " (11 chars) + "..." (3 chars) = 14 chars
            max_name_length = 80 - 14
            label = f"📄 Resume: {contact_name[:max_name_length]}..."

        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,
            custom_id=f"resume_{resume_id}",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle resume download button click."""
        try:
            # Get the CRM cog to access the API
            cog = interaction.client.get_cog("CRMCog")  # type: ignore[attr-defined]
            if not cog:
                await interaction.response.send_message(
                    "❌ CRM functionality not available.", ephemeral=True
                )
                return

            # Check if user has Member role
            if not cog._check_member_role(interaction):
                await interaction.response.send_message(
                    "❌ You must have the Member role to download resumes.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Use shared download method
            await cog._download_and_send_resume(
                interaction, self.contact_name, self.resume_id
            )

        except Exception as e:
            logger.error(f"Unexpected error in resume button callback: {e}")
            await interaction.followup.send(
                "❌ An unexpected error occurred while downloading the resume."
            )


class CRMCog(commands.Cog):
    """CRM integration cog for EspoCRM operations."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.espo_api = EspoAPI(settings.espo_api_url, settings.espo_api_key)

    async def _download_and_send_resume(
        self, interaction: discord.Interaction, contact_name: str, resume_id: str
    ) -> None:
        """Download and send a resume file as a Discord attachment."""
        try:
            # Download the resume file
            file_content = self.espo_api.download_file(f"Attachment/file/{resume_id}")

            # Get file metadata to determine filename
            file_info = self.espo_api.request("GET", f"Attachment/{resume_id}")
            filename = file_info.get("name", f"{contact_name}_resume.pdf")

            # Create Discord file object
            file_buffer = io.BytesIO(file_content)
            discord_file = discord.File(file_buffer, filename=filename)

            await interaction.followup.send(
                f"📄 Resume for **{contact_name}**:", file=discord_file
            )

        except EspoAPIError as e:
            logger.error(f"Failed to download resume {resume_id}: {e}")
            await interaction.followup.send(f"❌ Failed to download resume: {str(e)}")

    def _check_member_role(self, interaction: discord.Interaction) -> bool:
        """Check if user has Member role or higher for resume access."""
        if not hasattr(interaction.user, "roles"):
            return False
        return check_user_roles_with_hierarchy(interaction.user.roles, ["Member"])

    @app_commands.command(
        name="crm-contacts", description="Search for contacts in the CRM"
    )
    @app_commands.describe(
        query="Search term (name, Discord username, email, or 508 email)"
    )
    @require_role("Member")
    async def search_contacts(
        self, interaction: discord.Interaction, query: str
    ) -> None:
        """Search for contacts in the CRM."""
        try:
            await interaction.response.defer(ephemeral=True)

            # Search contacts using EspoCRM API
            search_params = {
                "where": [
                    {
                        "type": "or",
                        "value": [
                            {"type": "contains", "attribute": "name", "value": query},
                            {
                                "type": "contains",
                                "attribute": "cDiscordUsername",
                                "value": query,
                            },
                            {
                                "type": "contains",
                                "attribute": "emailAddress",
                                "value": query,
                            },
                            {
                                "type": "contains",
                                "attribute": "c508Email",
                                "value": query,
                            },
                        ],
                    }
                ],
                "maxSize": 10,
                "select": "id,name,emailAddress,c508Email,cDiscordUsername,phoneNumber,type,resumeIds,resumeNames,resumeTypes",
            }

            response = self.espo_api.request("GET", "Contact", search_params)
            contacts = response.get("list", [])

            if not contacts:
                await interaction.followup.send(f"🔍 No contacts found for: `{query}`")
                return

            logger.info(f"Found {len(contacts)} contacts for query: {query}")

            # Create embed with results
            embed = discord.Embed(
                title="🔍 CRM Contact Search Results",
                description=f"Found {len(contacts)} contact(s) for: `{query}`",
                color=0x0099FF,
            )

            # Create view with resume download buttons
            view = ResumeButtonView()

            for i, contact in enumerate(contacts):
                name = contact.get("name", "Unknown")
                email = contact.get("emailAddress", "No email")
                contact_type = contact.get("type", "Unknown")
                email_508 = contact.get("c508Email", "None")
                discord_username = contact.get("cDiscordUsername", "No Discord")

                contact_info = f"📧 {email}\n🏷️ Type: {contact_type}"

                # Only show 508 email and Discord for Candidates/Members
                if contact_type in ["Candidate / Member", "Member"]:
                    contact_info += (
                        f"\n🏢 508 Email: {email_508}\n💬 Discord: {discord_username}"
                    )

                embed.add_field(name=f"👤 {name}", value=contact_info, inline=True)

                # Check for resume data directly from search results
                resume_ids = contact.get("resumeIds", [])
                resume_names = contact.get("resumeNames", {})

                if resume_ids and len(resume_ids) > 0:
                    # Use the first resume ID
                    first_resume_id = resume_ids[0]
                    resume_name = resume_names.get(first_resume_id, f"{name}_resume")
                    logger.info(
                        f"Found resume for {name}: {resume_name} (ID: {first_resume_id})"
                    )
                    view.add_resume_button(name, first_resume_id)
                else:
                    logger.info(f"No resumes found for {name}")

            # Send embed with view only if there are buttons
            if view.children:
                await interaction.followup.send(embed=embed, view=view)
            else:
                await interaction.followup.send(embed=embed)

        except EspoAPIError as e:
            logger.error(f"EspoCRM API error: {e}")
            await interaction.followup.send(f"❌ CRM API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in CRM search: {e}")
            await interaction.followup.send(
                "❌ An unexpected error occurred while searching the CRM."
            )

    @app_commands.command(
        name="crm-status", description="Check CRM API connection status"
    )
    async def crm_status(self, interaction: discord.Interaction) -> None:
        """Check if the CRM API is accessible."""
        try:
            await interaction.response.defer(ephemeral=True)

            # Try a simple API call to check connectivity
            response = self.espo_api.request("GET", "App/user")
            user_name = response.get("user", {}).get("name", "Unknown")

            embed = discord.Embed(
                title="✅ CRM Status",
                description="Connection to EspoCRM is working!",
                color=0x00FF00,
            )
            embed.add_field(name="Connected as", value=user_name, inline=True)
            embed.add_field(name="API URL", value=settings.espo_api_url, inline=True)

            await interaction.followup.send(embed=embed)

        except EspoAPIError as e:
            logger.error(f"EspoCRM API error: {e}")
            embed = discord.Embed(
                title="❌ CRM Status",
                description=f"Failed to connect to EspoCRM: {str(e)}",
                color=0xFF0000,
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Unexpected error in CRM status: {e}")
            embed = discord.Embed(
                title="❌ CRM Status",
                description="An unexpected error occurred while checking CRM status.",
                color=0xFF0000,
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="get-resume", description="Download and send a contact's resume"
    )
    @app_commands.describe(
        query="Email address, 508 email (username, username@, or username@508.dev), or Discord username"
    )
    @require_role("Member")
    async def get_resume(self, interaction: discord.Interaction, query: str) -> None:
        """Download and send a contact's resume as a file attachment."""
        try:
            await interaction.response.defer(ephemeral=True)

            # Normalize the query - add @508.dev if it looks like a username or ends with @
            normalized_query = query
            if "@" not in query and not any(char in query for char in [" ", ".", "#"]):
                # Looks like a username, add @508.dev
                normalized_query = f"{query}@508.dev"
            elif query.endswith("@"):
                # Handle john@ -> john@508.dev
                normalized_query = f"{query}508.dev"

            # Search for the contact first
            search_params = {
                "where": [
                    {
                        "type": "or",
                        "value": [
                            {
                                "type": "contains",
                                "attribute": "emailAddress",
                                "value": normalized_query,
                            },
                            {
                                "type": "contains",
                                "attribute": "c508Email",
                                "value": normalized_query,
                            },
                            {
                                "type": "contains",
                                "attribute": "cDiscordUsername",
                                "value": query,  # Use original query for Discord username
                            },
                        ],
                    }
                ],
                "maxSize": 1,
                "select": "id,name,emailAddress,c508Email,cDiscordUsername,resumeIds,resumeNames,resumeTypes",
            }

            response = self.espo_api.request("GET", "Contact", search_params)
            contacts = response.get("list", [])

            if not contacts:
                await interaction.followup.send(f"❌ No contact found for: `{query}`")
                return

            contact = contacts[0]
            contact_name = contact.get("name", "Unknown")

            # Get resume data directly from search results
            resume_ids = contact.get("resumeIds", [])
            resume_names = contact.get("resumeNames", {})

            if not resume_ids or len(resume_ids) == 0:
                await interaction.followup.send(
                    f"❌ No resume found for {contact_name}"
                )
                return

            # Use the first resume
            resume_id = resume_ids[0]
            resume_name = resume_names.get(resume_id, f"{contact_name}_resume")

            logger.info(
                f"Downloading resume for {contact_name}: {resume_name} (ID: {resume_id})"
            )

            # Use shared download method
            await self._download_and_send_resume(interaction, contact_name, resume_id)

        except EspoAPIError as e:
            logger.error(f"EspoCRM API error in get_resume: {e}")
            await interaction.followup.send(f"❌ CRM API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in get_resume: {e}")
            await interaction.followup.send(
                "❌ An unexpected error occurred while fetching the resume."
            )


async def setup(bot: commands.Bot) -> None:
    """Add the CRM cog to the bot."""
    cog = CRMCog(bot)
    await bot.add_cog(cog)
    # Slash commands will be synced automatically in bot.py
