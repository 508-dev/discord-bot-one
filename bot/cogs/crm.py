"""
CRM integration cog for the 508.dev Discord bot.

This cog provides commands for interacting with EspoCRM through Discord slash commands.
It allows team members to quickly access CRM data without leaving Discord.
"""

import logging
import io
from typing import Any
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


class ContactSelectionView(discord.ui.View):
    """View containing contact selection buttons for Discord linking."""

    def __init__(self, user: discord.Member, search_term: str) -> None:
        super().__init__(timeout=300)  # 5 minute timeout
        self.user = user
        self.search_term = search_term

    def add_contact_button(self, contact: dict[str, Any]) -> None:
        """Add a contact selection button."""
        if len(self.children) >= 5:  # Discord limit of 5 buttons per row
            return

        button = ContactSelectionButton(contact, self.user)
        self.add_item(button)


class ContactSelectionButton(discord.ui.Button[ContactSelectionView]):
    """Button for selecting a contact to link to Discord user."""

    def __init__(self, contact: dict[str, Any], user: discord.Member) -> None:
        # Create button label from contact name (truncate if too long)
        contact_name = contact.get("name", "Unknown")
        label = contact_name[:80] if len(contact_name) > 80 else contact_name

        super().__init__(style=discord.ButtonStyle.primary, label=label, emoji="🔗")
        self.contact = contact
        self.user = user

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle contact selection and perform the Discord linking."""
        try:
            # Check if user has required role
            if not hasattr(
                interaction.user, "roles"
            ) or not check_user_roles_with_hierarchy(
                interaction.user.roles, ["Steering Committee"]
            ):
                await interaction.response.send_message(
                    "❌ You must have Steering Committee role or higher to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Get the CRM cog to perform the linking
            if not self.view:
                await interaction.followup.send("❌ View not found.")
                return

            from discord.ext import commands

            bot = interaction.client
            assert isinstance(bot, commands.Bot)
            cog = bot.get_cog("CRMCog")
            if not cog or not isinstance(cog, CRMCog):
                await interaction.followup.send("❌ CRM cog not found.")
                return

            # Perform the Discord linking
            success = await cog._perform_discord_linking(
                interaction, self.user, self.contact
            )

            if success and self.view:
                # Disable all buttons in the view
                for item in self.view.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled = True

                # Update the original message to show selection was made
                embed = discord.Embed(
                    title="✅ Contact Selected",
                    description=f"Selected **{self.contact.get('name', 'Unknown')}** for linking.",
                    color=0x00FF00,
                )

                # Edit the original message with disabled buttons
                if interaction.message:
                    try:
                        await interaction.message.edit(embed=embed, view=self.view)
                    except discord.NotFound:
                        # Message was deleted or not found, ignore this error
                        logger.debug(
                            "Original message not found when trying to update button view"
                        )
                    except discord.HTTPException as e:
                        # Other Discord API errors
                        logger.warning(f"Failed to update original message: {e}")

        except Exception as e:
            logger.error(f"Error in contact selection callback: {e}")
            await interaction.followup.send(
                "❌ An error occurred while linking the contact."
            )


class CRMCog(commands.Cog):
    """CRM integration cog for EspoCRM operations."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Construct API URL from base URL
        api_url = settings.espo_base_url.rstrip("/") + "/api/v1"
        self.espo_api = EspoAPI(api_url, settings.espo_api_key)
        # Store base URL for profile links
        self.base_url = settings.espo_base_url.rstrip("/")

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
                "select": "id,name,emailAddress,c508Email,cDiscordUsername,cDiscordUserID,phoneNumber,type,resumeIds,resumeNames,resumeTypes",
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
                discord_user_id = contact.get("cDiscordUserID")
                contact_id = contact.get("id", "")

                # Create Discord display with @mention if user ID exists
                # Remove "(ID: ...)" from stored username for cleaner display
                clean_discord_username = discord_username
                if " (ID: " in discord_username:
                    clean_discord_username = discord_username.split(" (ID: ")[0]

                discord_display = clean_discord_username
                if (
                    discord_user_id
                    and discord_user_id != "No Discord"
                    and interaction.guild
                ):
                    try:
                        # Try to get the Discord member for @mention
                        member = interaction.guild.get_member(int(discord_user_id))
                        if member:
                            discord_display = (
                                f"{member.mention} ({clean_discord_username})"
                            )
                    except (ValueError, AttributeError):
                        # If user ID is invalid or guild is None, just use username
                        pass

                contact_info = f"📧 {email}\n🏷️ Type: {contact_type}"

                # Only show 508 email and Discord for Candidates/Members
                if contact_type in ["Candidate / Member", "Member"]:
                    contact_info += (
                        f"\n🏢 508 Email: {email_508}\n💬 Discord: {discord_display}"
                    )

                # Add clickable CRM link at the top of contact info
                if contact_id:
                    profile_url = f"{self.base_url}/#Contact/view/{contact_id}"
                    contact_info = f"🔗 [View in CRM]({profile_url})\n{contact_info}"

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
            embed.add_field(name="Base URL", value=settings.espo_base_url, inline=True)

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

    def _is_hex_string(self, s: str) -> bool:
        """Check if string looks like a hex contact ID."""
        return len(s) >= 15 and all(c in "0123456789abcdefABCDEF" for c in s)

    async def _search_contact_for_linking(
        self, search_term: str
    ) -> list[dict[str, Any]]:
        """Search for contacts using multiple criteria."""
        # Check if it looks like a hex contact ID
        if self._is_hex_string(search_term):
            try:
                response = self.espo_api.request("GET", f"Contact/{search_term}")
                if response and response.get("id"):
                    return [response]
            except EspoAPIError:
                pass  # If direct ID lookup fails, fall through to regular search

        # Determine if this is an email search vs name search
        is_email = "@" in search_term
        has_space = " " in search_term

        # For email searches or full names (with space), auto-select if single result
        # For names without space, always show choices
        should_auto_select = is_email or has_space

        if is_email:
            # Email search - check both email fields
            normalized_email = search_term
            if "@" not in search_term.split("@")[-1]:  # Handle incomplete emails
                if search_term.endswith("@"):
                    normalized_email = f"{search_term}508.dev"
                elif "@" not in search_term:
                    normalized_email = f"{search_term}@508.dev"

            search_params = {
                "where": [
                    {
                        "type": "or",
                        "value": [
                            {
                                "type": "equals",
                                "attribute": "emailAddress",
                                "value": normalized_email,
                            },
                            {
                                "type": "equals",
                                "attribute": "c508Email",
                                "value": normalized_email,
                            },
                        ],
                    }
                ],
                "maxSize": 10,
                "select": "id,name,emailAddress,c508Email,cDiscordUsername",
            }
        else:
            # Name search
            search_params = {
                "where": [
                    {"type": "contains", "attribute": "name", "value": search_term}
                ],
                "maxSize": 10 if not should_auto_select else 1,
                "select": "id,name,emailAddress,c508Email,cDiscordUsername",
            }

        response = self.espo_api.request("GET", "Contact", search_params)
        contacts: list[dict[str, Any]] = response.get("list", [])

        # Deduplicate contacts by ID to avoid showing duplicates
        seen_ids = set()
        deduplicated_contacts = []
        for contact in contacts:
            contact_id = contact.get("id")
            if contact_id and contact_id not in seen_ids:
                seen_ids.add(contact_id)
                deduplicated_contacts.append(contact)

        # For email or full name searches, auto-select if exactly one result
        if should_auto_select and len(deduplicated_contacts) > 1:
            # Multiple results for email/full name - still show choices
            pass

        return deduplicated_contacts

    async def _perform_discord_linking(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        contact: dict[str, Any],
    ) -> bool:
        """Shared method to perform Discord user linking to a contact."""
        try:
            contact_id = contact.get("id")
            contact_name = contact.get("name", "Unknown")

            # Prepare the Discord username for storage (with ID) and display (without ID)
            if hasattr(user, "discriminator") and user.discriminator != "0":
                discord_info = f"{user.name}#{user.discriminator} (ID: {user.id})"
                discord_display = f"{user.name}#{user.discriminator}"
            else:
                discord_info = f"{user.name} (ID: {user.id})"
                discord_display = f"{user.name}"

            # Update the contact's Discord username and user ID
            update_data = {
                "cDiscordUsername": discord_info,
                "cDiscordUserID": str(user.id),
            }

            update_response = self.espo_api.request(
                "PUT", f"Contact/{contact_id}", update_data
            )

            if update_response:
                # Create success embed
                embed = discord.Embed(
                    title="✅ Discord User Linked",
                    description="Successfully linked Discord user to CRM contact (updated username and user ID)",
                    color=0x00FF00,
                )
                embed.add_field(
                    name="👤 Contact", value=f"{contact_name}", inline=False
                )
                embed.add_field(
                    name="📧 Email",
                    value=f"{contact.get('c508Email') or contact.get('emailAddress', 'N/A')}",
                    inline=True,
                )
                embed.add_field(
                    name="💬 Discord User",
                    value=f"{user.mention} ({discord_display})",
                    inline=True,
                )
                # Add CRM link
                if contact_id:
                    profile_url = f"{self.base_url}/#Contact/view/{contact_id}"
                    embed.add_field(
                        name="🔗 CRM Profile",
                        value=f"[View in CRM]({profile_url})",
                        inline=True,
                    )

                await interaction.followup.send(embed=embed)

                logger.info(
                    f"Discord user {user.name} (ID: {user.id}) linked to CRM contact "
                    f"{contact_name} (ID: {contact_id}) by {interaction.user.name}"
                )
                return True
            else:
                await interaction.followup.send(
                    "❌ Failed to update contact in CRM. Please try again."
                )
                return False

        except EspoAPIError as e:
            logger.error(f"EspoCRM API error in _perform_discord_linking: {e}")
            await interaction.followup.send(f"❌ CRM API error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in _perform_discord_linking: {e}")
            await interaction.followup.send(
                "❌ An unexpected error occurred while linking the user."
            )
            return False

    async def _show_contact_choices(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        search_term: str,
        contacts: list[dict[str, Any]],
    ) -> None:
        """Show contact choices when multiple results found."""
        embed = discord.Embed(
            title="🔍 Multiple Contacts Found",
            description=f"Found {len(contacts)} contacts for `{search_term}`. Click a button below to link the Discord user.",
            color=0xFFA500,
        )

        # Create view with contact selection buttons
        view = ContactSelectionView(user, search_term)

        for i, contact in enumerate(contacts[:5], 1):  # Show max 5
            name = contact.get("name", "Unknown")
            email = contact.get("emailAddress", "No email")
            email_508 = contact.get("c508Email", "No 508 email")
            contact_id = contact.get("id", "")

            contact_info = (
                f"📧 {email}\n🏢 508 Email: {email_508}\n🆔 ID: `{contact_id}`"
            )
            embed.add_field(name=f"{i}. {name}", value=contact_info, inline=True)

            # Add button for this contact
            view.add_contact_button(contact)

        embed.add_field(
            name="💡 Tip",
            value="Click the button for the contact you want to link, or use the contact ID for exact matching.",
            inline=False,
        )

        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(
        name="link-discord-user",
        description="Link a Discord user to a CRM contact (Steering Committee+ only)",
    )
    @app_commands.describe(
        user="Discord user to link (mention them)",
        search_term="Email, 508 email, name, or contact ID to find the contact",
    )
    @require_role("Steering Committee")
    async def link_discord_user(
        self, interaction: discord.Interaction, user: discord.Member, search_term: str
    ) -> None:
        """Link a Discord user to a CRM contact by updating the contact's Discord username."""
        try:
            await interaction.response.defer(ephemeral=True)

            # Determine search strategy based on search_term format
            contacts = await self._search_contact_for_linking(search_term)

            if not contacts:
                await interaction.followup.send(
                    f"❌ No contact found for: `{search_term}`"
                )
                return

            # Handle multiple results - show choices
            if len(contacts) > 1:
                await self._show_contact_choices(
                    interaction, user, search_term, contacts
                )
                return

            # Single result - proceed with linking
            contact = contacts[0]
            await self._perform_discord_linking(interaction, user, contact)

        except EspoAPIError as e:
            logger.error(f"EspoCRM API error in link_discord_user: {e}")
            await interaction.followup.send(f"❌ CRM API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in link_discord_user: {e}")
            await interaction.followup.send(
                "❌ An unexpected error occurred while linking the Discord user."
            )


async def setup(bot: commands.Bot) -> None:
    """Add the CRM cog to the bot."""
    cog = CRMCog(bot)
    await bot.add_cog(cog)
    # Slash commands will be synced automatically in bot.py
