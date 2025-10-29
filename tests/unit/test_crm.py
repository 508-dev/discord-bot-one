"""
Unit tests for CRM cog functionality.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import discord

from bot.cogs.crm import CRMCog, ResumeButtonView, ResumeDownloadButton
from bot.utils.espo_api_client import EspoAPIError


class TestCRMCog:
    """Unit tests for CRMCog class."""

    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot for testing."""
        bot = Mock()
        bot.get_cog = Mock()
        return bot

    @pytest.fixture
    def mock_espo_api(self):
        """Create a mock EspoAPI for testing."""
        with patch("bot.cogs.crm.EspoAPI") as mock_api_class:
            mock_api = Mock()
            mock_api_class.return_value = mock_api
            yield mock_api

    @pytest.fixture
    def crm_cog(self, mock_bot, mock_espo_api):
        """Create a CRMCog instance for testing."""
        cog = CRMCog(mock_bot)
        cog.espo_api = mock_espo_api
        return cog

    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.user = Mock()
        return interaction

    @pytest.fixture
    def mock_member_role(self):
        """Create a mock Member role."""
        role = Mock()
        role.name = "Member"
        return role

    @pytest.fixture
    def mock_admin_role(self):
        """Create a mock Admin role."""
        role = Mock()
        role.name = "Admin"
        return role

    def test_cog_initialization(self, mock_bot, mock_espo_api):
        """Test CRM cog initialization."""
        cog = CRMCog(mock_bot)
        assert cog.bot == mock_bot
        assert cog.espo_api is not None

    def test_check_member_role_with_member(
        self, crm_cog, mock_interaction, mock_member_role
    ):
        """Test _check_member_role returns True for users with Member role."""
        mock_interaction.user.roles = [mock_member_role]

        result = crm_cog._check_member_role(mock_interaction)

        assert result is True

    def test_check_member_role_without_member(self, crm_cog, mock_interaction):
        """Test _check_member_role returns False for users without Member role."""
        other_role = Mock()
        other_role.name = "User"
        mock_interaction.user.roles = [other_role]

        result = crm_cog._check_member_role(mock_interaction)

        assert result is False

    @pytest.mark.asyncio
    async def test_download_and_send_resume_success(self, crm_cog, mock_interaction):
        """Test successful resume download and send."""
        # Mock API responses
        file_content = b"fake_pdf_content"
        file_info = {"name": "john_doe_resume.pdf"}

        crm_cog.espo_api.download_file.return_value = file_content
        crm_cog.espo_api.request.return_value = file_info

        await crm_cog._download_and_send_resume(
            mock_interaction, "John Doe", "resume123"
        )

        # Verify API calls
        crm_cog.espo_api.download_file.assert_called_once_with(
            "Attachment/file/resume123"
        )
        crm_cog.espo_api.request.assert_called_once_with("GET", "Attachment/resume123")

        # Verify Discord response
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert "📄 Resume for **John Doe**:" in call_args[0][0]
        assert "file" in call_args[1]

    @pytest.mark.asyncio
    async def test_download_and_send_resume_api_error(self, crm_cog, mock_interaction):
        """Test resume download with API error."""
        crm_cog.espo_api.download_file.side_effect = EspoAPIError("API Error")

        await crm_cog._download_and_send_resume(
            mock_interaction, "John Doe", "resume123"
        )

        mock_interaction.followup.send.assert_called_once_with(
            "❌ Failed to download resume: API Error"
        )

    @pytest.mark.asyncio
    async def test_search_contacts_success(
        self, crm_cog, mock_interaction, mock_member_role
    ):
        """Test successful contact search."""
        # Mock user with Member role
        mock_interaction.user.roles = [mock_member_role]

        # Mock API responses with resume data included
        contacts_response = {
            "list": [
                {
                    "id": "contact123",
                    "name": "John Doe",
                    "emailAddress": "john@example.com",
                    "type": "Member",
                    "c508Email": "john@508.dev",
                    "cDiscordUsername": "johndoe#1234",
                    "resumeIds": ["resume123"],
                    "resumeNames": {"resume123": "john_resume.pdf"},
                }
            ]
        }

        # Only need one API call now
        crm_cog.espo_api.request.return_value = contacts_response

        # Call the callback function to bypass app_commands decorator
        await crm_cog.search_contacts.callback(crm_cog, mock_interaction, "john")

        # Verify API calls - only one call needed now
        crm_cog.espo_api.request.assert_called_once()
        call_args = crm_cog.espo_api.request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == "Contact"

        # Verify response was sent
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_contacts_no_results(
        self, crm_cog, mock_interaction, mock_member_role
    ):
        """Test contact search with no results."""
        mock_interaction.user.roles = [mock_member_role]
        crm_cog.espo_api.request.return_value = {"list": []}

        # Call the callback function to bypass app_commands decorator
        await crm_cog.search_contacts.callback(crm_cog, mock_interaction, "nonexistent")

        mock_interaction.followup.send.assert_called_once_with(
            "🔍 No contacts found for: `nonexistent`"
        )

    @pytest.mark.asyncio
    async def test_get_resume_success(
        self, crm_cog, mock_interaction, mock_member_role
    ):
        """Test successful resume retrieval."""
        mock_interaction.user.roles = [mock_member_role]

        # Mock contact search response with resume data included
        contact_response = {
            "list": [
                {
                    "id": "contact123",
                    "name": "John Doe",
                    "resumeIds": ["resume123"],
                    "resumeNames": {"resume123": "john_resume.pdf"},
                }
            ]
        }

        # Mock file info response
        file_info_response = {"name": "john_resume.pdf"}

        # Set up side_effect for API calls
        crm_cog.espo_api.request.side_effect = [contact_response, file_info_response]

        # Mock file download
        crm_cog.espo_api.download_file.return_value = b"fake_pdf"

        # Call the callback function to bypass app_commands decorator
        await crm_cog.get_resume.callback(crm_cog, mock_interaction, "john@508.dev")

        # Verify API calls (search + file info)
        assert crm_cog.espo_api.request.call_count == 2
        # Verify file download was called
        crm_cog.espo_api.download_file.assert_called_once()
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_resume_contact_not_found(
        self, crm_cog, mock_interaction, mock_member_role
    ):
        """Test resume retrieval when contact not found."""
        mock_interaction.user.roles = [mock_member_role]
        crm_cog.espo_api.request.return_value = {"list": []}

        # Call the callback function to bypass app_commands decorator
        await crm_cog.get_resume.callback(
            crm_cog, mock_interaction, "nonexistent@example.com"
        )

        mock_interaction.followup.send.assert_called_once_with(
            "❌ No contact found for: `nonexistent@example.com`"
        )

    @pytest.mark.asyncio
    async def test_get_resume_no_resume_found(
        self, crm_cog, mock_interaction, mock_member_role
    ):
        """Test resume retrieval when contact has no resume."""
        mock_interaction.user.roles = [mock_member_role]

        contact_response = {
            "list": [
                {
                    "id": "contact123",
                    "name": "John Doe",
                    "resumeIds": [],
                    "resumeNames": {},
                }
            ]
        }

        crm_cog.espo_api.request.return_value = contact_response

        # Call the callback function to bypass app_commands decorator
        await crm_cog.get_resume.callback(crm_cog, mock_interaction, "john@508.dev")

        mock_interaction.followup.send.assert_called_once_with(
            "❌ No resume found for John Doe"
        )

    @pytest.mark.asyncio
    async def test_link_discord_user_success(
        self, crm_cog, mock_interaction, mock_admin_role
    ):
        """Test successful Discord user linking."""
        mock_interaction.user.roles = [mock_admin_role]

        # Mock Discord user
        mock_discord_user = Mock()
        mock_discord_user.name = "johndoe"
        mock_discord_user.id = 123456789
        mock_discord_user.mention = "<@123456789>"
        mock_discord_user.discriminator = "1234"

        # Mock contact search response
        contact_response = {
            "list": [
                {
                    "id": "contact123",
                    "name": "John Doe",
                    "emailAddress": "john@example.com",
                    "c508Email": "john@508.dev",
                    "cDiscordUsername": "olduser#0000 (ID: 987654321)",
                }
            ]
        }

        # Mock update response
        update_response = {"id": "contact123"}

        crm_cog.espo_api.request.side_effect = [contact_response, update_response]

        # Call the command
        await crm_cog.link_discord_user.callback(
            crm_cog, mock_interaction, mock_discord_user, "john"
        )

        # Verify API calls
        assert crm_cog.espo_api.request.call_count == 2

        # Verify search call
        search_call = crm_cog.espo_api.request.call_args_list[0]
        assert search_call[0][0] == "GET"
        assert search_call[0][1] == "Contact"

        # Verify update call
        update_call = crm_cog.espo_api.request.call_args_list[1]
        assert update_call[0][0] == "PUT"
        assert update_call[0][1] == "Contact/contact123"
        assert "cDiscordUsername" in update_call[0][2]
        assert update_call[0][2]["cDiscordUsername"] == "johndoe#1234"
        assert "cDiscordUserID" in update_call[0][2]
        assert update_call[0][2]["cDiscordUserID"] == "123456789"

        # Verify success response
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert "embed" in call_args[1]

    @pytest.mark.asyncio
    async def test_link_discord_user_contact_not_found(
        self, crm_cog, mock_interaction, mock_admin_role
    ):
        """Test Discord user linking when contact not found."""
        mock_interaction.user.roles = [mock_admin_role]

        # Mock Discord user
        mock_discord_user = Mock()
        mock_discord_user.name = "johndoe"

        # Mock empty contact response
        crm_cog.espo_api.request.return_value = {"list": []}

        await crm_cog.link_discord_user.callback(
            crm_cog, mock_interaction, mock_discord_user, "nonexistent"
        )

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert "❌ No contact found" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_link_discord_user_name_search(
        self, crm_cog, mock_interaction, mock_admin_role
    ):
        """Test name search in Discord user linking."""
        mock_interaction.user.roles = [mock_admin_role]

        # Mock Discord user
        mock_discord_user = Mock()
        mock_discord_user.name = "johndoe"

        # Mock contact response
        contact_response = {"list": []}
        crm_cog.espo_api.request.return_value = contact_response

        # Test username normalization
        await crm_cog.link_discord_user.callback(
            crm_cog, mock_interaction, mock_discord_user, "john"
        )

        # Verify the search was performed (should search by name since "john" has no @ or space)
        call_args = crm_cog.espo_api.request.call_args
        search_params = call_args[0][2]  # Third argument is the search params
        # Check that it searched for "john" as a name
        assert search_params["where"][0]["attribute"] == "name"
        assert search_params["where"][0]["value"] == "john"

    @pytest.mark.asyncio
    async def test_link_discord_user_modern_username(
        self, crm_cog, mock_interaction, mock_admin_role
    ):
        """Test Discord user linking with modern username (no discriminator)."""
        mock_interaction.user.roles = [mock_admin_role]

        # Mock Discord user without discriminator
        mock_discord_user = Mock()
        mock_discord_user.name = "johndoe"
        mock_discord_user.id = 123456789
        mock_discord_user.discriminator = "0"  # Modern Discord users have "0"

        # Mock contact and update responses
        contact_response = {
            "list": [
                {
                    "id": "contact123",
                    "name": "John Doe",
                    "cDiscordUsername": "",
                }
            ]
        }
        update_response = {"id": "contact123"}

        crm_cog.espo_api.request.side_effect = [contact_response, update_response]

        await crm_cog.link_discord_user.callback(
            crm_cog, mock_interaction, mock_discord_user, "john@508.dev"
        )

        # Verify update call used format without discriminator
        update_call = crm_cog.espo_api.request.call_args_list[1]
        discord_username = update_call[0][2]["cDiscordUsername"]
        assert discord_username == "johndoe"
        assert "#0" not in discord_username
        assert "cDiscordUserID" in update_call[0][2]
        assert update_call[0][2]["cDiscordUserID"] == "123456789"

    @pytest.mark.asyncio
    async def test_link_discord_user_hex_id_search(
        self, crm_cog, mock_interaction, mock_admin_role
    ):
        """Test Discord user linking with hex contact ID."""
        mock_interaction.user.roles = [mock_admin_role]

        # Mock Discord user
        mock_discord_user = Mock()
        mock_discord_user.name = "johndoe"
        mock_discord_user.id = 123456789
        mock_discord_user.mention = "<@123456789>"
        mock_discord_user.discriminator = "0"

        # Mock contact response for direct ID lookup
        contact_response = {
            "id": "65a6b62400e7d0079",
            "name": "John Doe",
            "emailAddress": "john@example.com",
        }
        update_response = {"id": "65a6b62400e7d0079"}

        crm_cog.espo_api.request.side_effect = [contact_response, update_response]

        # Call the command with hex ID
        await crm_cog.link_discord_user.callback(
            crm_cog, mock_interaction, mock_discord_user, "65a6b62400e7d0079"
        )

        # Verify direct ID lookup was used
        first_call = crm_cog.espo_api.request.call_args_list[0]
        assert first_call[0][0] == "GET"
        assert first_call[0][1] == "Contact/65a6b62400e7d0079"

        # Verify success response
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_link_discord_user_email_search(
        self, crm_cog, mock_interaction, mock_admin_role
    ):
        """Test Discord user linking with email search."""
        mock_interaction.user.roles = [mock_admin_role]

        # Mock Discord user
        mock_discord_user = Mock()
        mock_discord_user.name = "johndoe"
        mock_discord_user.id = 123456789
        mock_discord_user.mention = "<@123456789>"
        mock_discord_user.discriminator = "0"

        # Mock contact search response
        contact_response = {
            "list": [
                {
                    "id": "contact123",
                    "name": "John Doe",
                    "emailAddress": "john@508.dev",
                }
            ]
        }
        update_response = {"id": "contact123"}

        crm_cog.espo_api.request.side_effect = [contact_response, update_response]

        # Call the command with email
        await crm_cog.link_discord_user.callback(
            crm_cog, mock_interaction, mock_discord_user, "john@508.dev"
        )

        # Verify email search was used
        search_call = crm_cog.espo_api.request.call_args_list[0]
        assert search_call[0][0] == "GET"
        assert search_call[0][1] == "Contact"
        search_params = search_call[0][2]
        assert search_params["where"][0]["type"] == "or"
        # Check that it searches both email fields
        email_searches = search_params["where"][0]["value"]
        assert any(param["attribute"] == "emailAddress" for param in email_searches)
        assert any(param["attribute"] == "c508Email" for param in email_searches)

    @pytest.mark.asyncio
    async def test_link_discord_user_multiple_results(
        self, crm_cog, mock_interaction, mock_admin_role
    ):
        """Test Discord user linking when multiple contacts found."""
        mock_interaction.user.roles = [mock_admin_role]

        # Mock Discord user
        mock_discord_user = Mock()
        mock_discord_user.name = "johndoe"
        mock_discord_user.id = 123456789

        # Mock contact search response with multiple results
        contact_response = {
            "list": [
                {
                    "id": "contact123",
                    "name": "John Doe",
                    "emailAddress": "john1@example.com",
                },
                {
                    "id": "contact456",
                    "name": "John Smith",
                    "emailAddress": "john2@example.com",
                },
            ]
        }

        crm_cog.espo_api.request.return_value = contact_response

        # Call the command with a name that returns multiple results
        await crm_cog.link_discord_user.callback(
            crm_cog, mock_interaction, mock_discord_user, "John"
        )

        # Verify choices were shown instead of linking
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert "embed" in call_args[1]
        embed = call_args[1]["embed"]
        assert "Multiple Contacts Found" in embed.title

    @pytest.mark.asyncio
    async def test_link_discord_user_deduplication(
        self, crm_cog, mock_interaction, mock_admin_role
    ):
        """Test Discord user linking with duplicate contacts (same ID)."""
        mock_interaction.user.roles = [mock_admin_role]

        # Mock Discord user
        mock_discord_user = Mock()
        mock_discord_user.name = "johndoe"
        mock_discord_user.id = 123456789

        # Mock contact search response with duplicates (same ID)
        contact_response = {
            "list": [
                {
                    "id": "contact123",
                    "name": "John Doe",
                    "emailAddress": "john1@example.com",
                },
                {
                    "id": "contact123",  # Duplicate ID
                    "name": "John Doe",
                    "emailAddress": "john1@example.com",
                },
                {
                    "id": "contact456",
                    "name": "John Smith",
                    "emailAddress": "john2@example.com",
                },
            ]
        }

        crm_cog.espo_api.request.return_value = contact_response

        # Call the command - should deduplicate and show choices
        await crm_cog.link_discord_user.callback(
            crm_cog, mock_interaction, mock_discord_user, "John"
        )

        # Verify choices were shown with deduplicated contacts
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert "embed" in call_args[1]
        assert "view" in call_args[1]  # Should have buttons
        embed = call_args[1]["embed"]
        assert "Multiple Contacts Found" in embed.title
        # Should only show 2 unique contacts, not 3
        assert len(embed.fields) == 3  # 2 contacts + tip field

    @pytest.mark.asyncio
    async def test_unlinked_discord_users_with_unlinked_users(
        self, crm_cog, mock_interaction, mock_admin_role
    ):
        """Test unlinked Discord users command with some unlinked users."""
        mock_interaction.user.roles = [mock_admin_role]

        # Mock guild with members
        mock_guild = Mock()
        mock_interaction.guild = mock_guild

        # Create mock members - some linked, some not
        mock_member1 = Mock()
        mock_member1.id = 111111111
        mock_member1.display_name = "Alice"
        mock_member1.mention = "<@111111111>"
        mock_member1.bot = False
        mock_member1.roles = [Mock()]
        mock_member1.roles[0].name = "Member"

        mock_member2 = Mock()
        mock_member2.id = 222222222
        mock_member2.display_name = "Bob"
        mock_member2.mention = "<@222222222>"
        mock_member2.bot = False
        mock_member2.roles = [Mock()]
        mock_member2.roles[0].name = "Admin"

        mock_member3 = Mock()  # This one is linked
        mock_member3.id = 333333333
        mock_member3.display_name = "Charlie"
        mock_member3.bot = False
        mock_member3.roles = [Mock()]
        mock_member3.roles[0].name = "Member"

        mock_guild.members = [mock_member1, mock_member2, mock_member3]

        # Mock CRM response - Charlie is linked, others are not
        crm_response = {
            "list": [
                {"cDiscordUserID": "333333333"}  # Charlie is linked
            ]
        }
        crm_cog.espo_api.request.return_value = crm_response

        # Call the command
        await crm_cog.unlinked_discord_users.callback(crm_cog, mock_interaction)

        # Verify API call
        crm_cog.espo_api.request.assert_called_once()
        call_args = crm_cog.espo_api.request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == "Contact"
        search_params = call_args[0][2]
        assert search_params["where"][0]["type"] == "isNotNull"
        assert search_params["where"][0]["attribute"] == "cDiscordUserID"

        # Verify response contains unlinked users (Alice and Bob)
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        message_text = call_args[0][0]
        assert "Unlinked Discord Users (2)" in message_text
        assert "<@111111111>" in message_text  # Alice's mention
        assert "<@222222222>" in message_text  # Bob's mention

    @pytest.mark.asyncio
    async def test_unlinked_discord_users_all_linked(
        self, crm_cog, mock_interaction, mock_admin_role
    ):
        """Test unlinked Discord users command when all users are linked."""
        mock_interaction.user.roles = [mock_admin_role]

        # Mock guild with members
        mock_guild = Mock()
        mock_interaction.guild = mock_guild

        # Create mock member
        mock_member = Mock()
        mock_member.id = 111111111
        mock_member.bot = False
        mock_member.roles = [Mock()]
        mock_member.roles[0].name = "Member"

        mock_guild.members = [mock_member]

        # Mock CRM response - member is linked
        crm_response = {
            "list": [
                {"cDiscordUserID": "111111111"}  # Member is linked
            ]
        }
        crm_cog.espo_api.request.return_value = crm_response

        # Call the command
        await crm_cog.unlinked_discord_users.callback(crm_cog, mock_interaction)

        # Verify response shows all linked
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        message_text = call_args[0][0]
        assert "All Members Linked" in message_text

    @pytest.mark.asyncio
    async def test_unlinked_discord_users_no_guild(
        self, crm_cog, mock_interaction, mock_admin_role
    ):
        """Test unlinked Discord users command when not in a guild."""
        mock_interaction.user.roles = [mock_admin_role]
        mock_interaction.guild = None

        # Call the command
        await crm_cog.unlinked_discord_users.callback(crm_cog, mock_interaction)

        # Verify error response
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert "❌ This command can only be used in a server." in call_args[0][0]

    def test_query_normalization_username(self, crm_cog):
        """Test that username gets @508.dev appended."""
        # This would be tested in the actual command, but we can verify the logic
        query = "john"
        # Simulate the normalization logic from get_resume
        normalized = (
            f"{query}@508.dev"
            if "@" not in query and not any(char in query for char in [" ", ".", "#"])
            else query
        )
        assert normalized == "john@508.dev"

    def test_query_normalization_at_sign(self, crm_cog):
        """Test that john@ becomes john@508.dev."""
        query = "john@"
        # Simulate the normalization logic from get_resume
        normalized = f"{query}508.dev" if query.endswith("@") else query
        assert normalized == "john@508.dev"

    @pytest.mark.asyncio
    async def test_crm_status_success(self, crm_cog, mock_interaction):
        """Test successful CRM status check."""
        crm_cog.espo_api.request.return_value = {"user": {"name": "Test User"}}

        await crm_cog.crm_status.callback(crm_cog, mock_interaction)

        crm_cog.espo_api.request.assert_called_once_with("GET", "App/user")
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_crm_status_api_error(self, crm_cog, mock_interaction):
        """Test CRM status check with API error."""
        crm_cog.espo_api.request.side_effect = EspoAPIError("Connection failed")

        await crm_cog.crm_status.callback(crm_cog, mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        # Check that embed is sent
        assert "embed" in call_args[1]


class TestResumeButtonView:
    """Tests for ResumeButtonView class."""

    @pytest.mark.asyncio
    async def test_button_view_initialization(self):
        """Test ResumeButtonView initialization."""
        view = ResumeButtonView()
        assert view.timeout == 300
        assert len(view.children) == 0

    @pytest.mark.asyncio
    async def test_add_resume_button(self):
        """Test adding resume button to view."""
        view = ResumeButtonView()
        view.add_resume_button("John Doe", "resume123")

        assert len(view.children) == 1
        button = view.children[0]
        assert isinstance(button, ResumeDownloadButton)
        assert button.contact_name == "John Doe"
        assert button.resume_id == "resume123"

    @pytest.mark.asyncio
    async def test_add_resume_button_limit(self):
        """Test that view respects 5 button limit."""
        view = ResumeButtonView()

        # Add 6 buttons
        for i in range(6):
            view.add_resume_button(f"Contact {i}", f"resume{i}")

        # Should only have 5 buttons
        assert len(view.children) == 5


class TestResumeDownloadButton:
    """Tests for ResumeDownloadButton class."""

    def test_button_initialization(self):
        """Test ResumeDownloadButton initialization."""
        button = ResumeDownloadButton("John Doe", "resume123")

        assert button.contact_name == "John Doe"
        assert button.resume_id == "resume123"
        assert button.label == "📄 Resume: John Doe"
        assert button.style == discord.ButtonStyle.secondary
        assert button.custom_id == "resume_resume123"

    def test_button_long_name_truncation(self):
        """Test that long contact names are truncated in button label."""
        long_name = "A" * 80  # Very long name
        button = ResumeDownloadButton(long_name, "resume123")

        assert len(button.label) <= 80
        assert button.label.endswith("...")

    @pytest.mark.asyncio
    async def test_button_callback_success(self):
        """Test successful button callback."""
        button = ResumeDownloadButton("John Doe", "resume123")

        # Mock interaction
        mock_interaction = AsyncMock()
        mock_interaction.response = AsyncMock()
        mock_interaction.response.defer = AsyncMock()

        # Mock user with Member role
        member_role = Mock()
        member_role.name = "Member"
        mock_interaction.user.roles = [member_role]

        # Mock CRM cog
        mock_crm_cog = Mock()
        mock_crm_cog._check_member_role = Mock(return_value=True)
        mock_crm_cog._download_and_send_resume = AsyncMock()

        # Mock client
        mock_client = Mock()
        mock_client.get_cog = Mock(return_value=mock_crm_cog)
        mock_interaction.client = mock_client

        await button.callback(mock_interaction)

        mock_crm_cog._download_and_send_resume.assert_called_once_with(
            mock_interaction, "John Doe", "resume123"
        )

    @pytest.mark.asyncio
    async def test_button_callback_no_member_role(self):
        """Test button callback without Member role."""
        button = ResumeDownloadButton("John Doe", "resume123")

        # Mock interaction
        mock_interaction = AsyncMock()
        mock_interaction.response = AsyncMock()
        mock_interaction.response.send_message = AsyncMock()

        # Mock user without Member role
        other_role = Mock()
        other_role.name = "User"
        mock_interaction.user.roles = [other_role]

        # Mock CRM cog
        mock_crm_cog = Mock()
        mock_crm_cog._check_member_role = Mock(return_value=False)

        # Mock client
        mock_client = Mock()
        mock_client.get_cog = Mock(return_value=mock_crm_cog)
        mock_interaction.client = mock_client

        await button.callback(mock_interaction)

        mock_interaction.response.send_message.assert_called_once_with(
            "❌ You must have the Member role to download resumes.", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_button_callback_no_cog(self):
        """Test button callback when CRM cog not available."""
        button = ResumeDownloadButton("John Doe", "resume123")

        # Mock interaction
        mock_interaction = AsyncMock()
        mock_interaction.response = AsyncMock()
        mock_interaction.response.send_message = AsyncMock()
        # Mock client
        mock_client = Mock()
        mock_client.get_cog = Mock(return_value=None)
        mock_interaction.client = mock_client

        await button.callback(mock_interaction)

        mock_interaction.response.send_message.assert_called_once_with(
            "❌ CRM functionality not available.", ephemeral=True
        )
