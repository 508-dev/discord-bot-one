"""
Tests for the CRM data adapter.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock

from bot.utils.crm_cache import CRMDataAdapter
from bot.utils.data_store import ServiceDataStore
from bot.utils.espo_api_client import EspoAPI, EspoAPIError


class TestCRMDataAdapter:
    """Test cases for the CRMDataAdapter class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def data_store(self, temp_db):
        """Create a ServiceDataStore instance with temporary database."""
        return ServiceDataStore(temp_db)

    @pytest.fixture
    def mock_espo_api(self):
        """Create a mock EspoAPI instance."""
        mock_api = Mock(spec=EspoAPI)
        return mock_api

    @pytest.fixture
    def crm_adapter(self, mock_espo_api, data_store):
        """Create a CRMDataAdapter instance."""
        return CRMDataAdapter(mock_espo_api, data_store)

    @pytest.fixture
    def sample_member_contact_data(self):
        """Sample contact data for a member."""
        return {
            "id": "contact123",
            "name": "John Doe",
            "emailAddress": "john@example.com",
            "c508Email": "john@508.dev",
            "cDiscordUsername": "johndoe#1234",
            "cDiscordUserID": "123456789",
            "cGitHubUsername": "johndoe",
            "type": "Member",
            "resumeIds": ["resume1", "resume2"],
            "resumeNames": {"resume1": "John_Resume.pdf", "resume2": "John_CV.pdf"},
            "resumeTypes": {"resume1": "application/pdf", "resume2": "application/pdf"},
        }

    @pytest.fixture
    def sample_candidate_contact_data(self):
        """Sample contact data for a candidate."""
        return {
            "id": "contact456",
            "name": "Jane Smith",
            "emailAddress": "jane@example.com",
            "c508Email": None,
            "cDiscordUsername": "janesmith#5678",
            "cDiscordUserID": "987654321",
            "cGitHubUsername": "janesmith",
            "type": "Candidate",
        }

    @pytest.mark.asyncio
    async def test_initialization(self, crm_adapter, mock_espo_api):
        """Test that CRM adapter initializes correctly."""
        # Mock the API response for loading all members and candidates
        mock_espo_api.request.return_value = {
            "list": [
                {
                    "id": "contact123",
                    "name": "John Doe",
                    "c508Email": "john@508.dev",
                    "cDiscordUserID": "123456789",
                    "type": "Member",
                },
                {
                    "id": "contact456",
                    "name": "Jane Smith",
                    "emailAddress": "jane@example.com",
                    "cDiscordUserID": "987654321",
                    "type": "Candidate",
                },
            ]
        }

        await crm_adapter.initialize()

        # Verify API was called to load members and candidates
        mock_espo_api.request.assert_called_once()
        call_args = mock_espo_api.request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == "Contact"
        # Check that the search includes Member, Candidate, and legacy types
        search_params = call_args[0][2]
        assert "where" in search_params
        assert "or" in str(search_params["where"])

    @pytest.mark.asyncio
    async def test_cache_contact_member(self, crm_adapter, sample_member_contact_data):
        """Test caching a member contact."""
        await crm_adapter._cache_contact(sample_member_contact_data)

        # Verify member was created
        member_data = crm_adapter.data_store.get_member_by_discord_id("123456789")
        assert member_data is not None
        assert member_data["member"]["email_508"] == "john@508.dev"
        assert member_data["member"]["discord_user_id"] == "123456789"
        assert member_data["member"]["display_name"] == "John Doe"
        assert member_data["member"]["member_type"] == "member"

        # Verify service data was stored
        assert "espocrm" in member_data["services"]
        assert "contact" in member_data["services"]["espocrm"]
        contact_data = member_data["services"]["espocrm"]["contact"][0]["data"]
        assert contact_data["id"] == "contact123"
        assert contact_data["name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_cache_contact_candidate(
        self, crm_adapter, sample_candidate_contact_data
    ):
        """Test caching a candidate contact."""
        await crm_adapter._cache_contact(sample_candidate_contact_data)

        # Verify member was created as candidate
        member_data = crm_adapter.data_store.get_member_by_discord_id("987654321")
        assert member_data is not None
        assert member_data["member"]["email_508"] is None
        assert member_data["member"]["email_other"] == "jane@example.com"
        assert member_data["member"]["discord_user_id"] == "987654321"
        assert member_data["member"]["display_name"] == "Jane Smith"
        assert member_data["member"]["member_type"] == "candidate"

    @pytest.mark.asyncio
    async def test_cache_contact_no_508_email(self, crm_adapter):
        """Test caching a contact with no 508 email."""
        contact_data = {
            "id": "contact789",
            "name": "Bob Johnson",
            "emailAddress": "bob@example.com",
            "c508Email": "None",  # String "None" should be treated as null
            "cDiscordUserID": "555666777",
            "type": "Candidate",
        }

        await crm_adapter._cache_contact(contact_data)

        member_data = crm_adapter.data_store.get_member_by_discord_id("555666777")
        assert member_data is not None
        assert member_data["member"]["email_508"] is None
        assert member_data["member"]["email_other"] == "bob@example.com"
        assert member_data["member"]["member_type"] == "candidate"

    @pytest.mark.asyncio
    async def test_cache_contact_regular_email_as_508(self, crm_adapter):
        """Test caching a contact where emailAddress is a 508.dev email."""
        contact_data = {
            "id": "contact999",
            "name": "Alice Wonder",
            "emailAddress": "alice@508.dev",
            "c508Email": None,
            "cDiscordUserID": "111222333",
            "type": "Member",
        }

        await crm_adapter._cache_contact(contact_data)

        member_data = crm_adapter.data_store.get_member_by_discord_id("111222333")
        assert member_data is not None
        assert member_data["member"]["email_508"] == "alice@508.dev"
        assert member_data["member"]["email_other"] is None
        assert member_data["member"]["member_type"] == "member"

    @pytest.mark.asyncio
    async def test_find_contact_by_discord_id_cache_hit(
        self, crm_adapter, sample_member_contact_data
    ):
        """Test finding a contact by Discord ID with cache hit."""
        # Pre-cache the contact
        await crm_adapter._cache_contact(sample_member_contact_data)

        # Find contact
        result = await crm_adapter.find_contact_by_discord_id("123456789")

        assert result is not None
        assert result["id"] == "contact123"
        assert result["name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_find_contact_by_discord_id_cache_miss(
        self, crm_adapter, mock_espo_api
    ):
        """Test finding a contact by Discord ID with cache miss."""
        # Mock API response
        mock_espo_api.request.return_value = {
            "list": [
                {
                    "id": "contact456",
                    "name": "Jane Smith",
                    "emailAddress": "jane@example.com",
                    "cDiscordUserID": "987654321",
                    "type": "Candidate",
                }
            ]
        }

        result = await crm_adapter.find_contact_by_discord_id("987654321")

        assert result is not None
        assert result["id"] == "contact456"
        assert result["name"] == "Jane Smith"

        # Verify API was called
        mock_espo_api.request.assert_called_once()

        # Verify contact was cached for future use
        member_data = crm_adapter.data_store.get_member_by_discord_id("987654321")
        assert member_data is not None

    @pytest.mark.asyncio
    async def test_find_member_by_discord_id(
        self, crm_adapter, sample_member_contact_data
    ):
        """Test finding a member by Discord ID."""
        # Pre-cache the contact
        await crm_adapter._cache_contact(sample_member_contact_data)

        # Find member
        result = await crm_adapter.find_member_by_discord_id("123456789")

        assert result is not None
        assert result["member"]["email_508"] == "john@508.dev"
        assert result["member"]["discord_user_id"] == "123456789"
        assert "espocrm" in result["services"]

    @pytest.mark.asyncio
    async def test_find_member_by_email(self, crm_adapter, sample_member_contact_data):
        """Test finding a member by email."""
        # Pre-cache the contact
        await crm_adapter._cache_contact(sample_member_contact_data)

        # Find member by 508 email
        result = await crm_adapter.find_member_by_email("john@508.dev")

        assert result is not None
        assert result["member"]["email_508"] == "john@508.dev"
        assert result["member"]["discord_user_id"] == "123456789"

    @pytest.mark.asyncio
    async def test_get_contact_by_id_cache_hit(
        self, crm_adapter, sample_member_contact_data
    ):
        """Test getting a contact by ID with cache hit."""
        # Pre-cache the contact
        await crm_adapter._cache_contact(sample_member_contact_data)

        result = await crm_adapter.get_contact_by_id("contact123")

        assert result is not None
        assert result["id"] == "contact123"
        assert result["name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_get_contact_by_id_force_refresh(self, crm_adapter, mock_espo_api):
        """Test getting a contact by ID with forced refresh."""
        # Mock API response
        mock_espo_api.request.return_value = {
            "id": "contact789",
            "name": "Refreshed Contact",
            "type": "Member",
        }

        result = await crm_adapter.get_contact_by_id("contact789", force_refresh=True)

        assert result is not None
        assert result["id"] == "contact789"
        assert result["name"] == "Refreshed Contact"

        # Verify API was called
        mock_espo_api.request.assert_called_once_with("GET", "Contact/contact789")

    @pytest.mark.asyncio
    async def test_search_contacts_cache_miss(self, crm_adapter, mock_espo_api):
        """Test searching contacts with cache miss."""
        search_params = {
            "where": [{"type": "equals", "attribute": "name", "value": "John"}]
        }

        # Mock API response
        mock_espo_api.request.return_value = {
            "list": [
                {
                    "id": "contact123",
                    "name": "John Doe",
                    "type": "Member",
                }
            ],
            "total": 1,
        }

        result = await crm_adapter.search_contacts(search_params)

        assert result is not None
        assert "list" in result
        assert len(result["list"]) == 1
        assert result["list"][0]["name"] == "John Doe"

        # Verify API was called
        mock_espo_api.request.assert_called_once_with("GET", "Contact", search_params)

    @pytest.mark.asyncio
    async def test_update_contact(self, crm_adapter, mock_espo_api):
        """Test updating a contact."""
        update_data = {"name": "John Updated"}

        # Mock successful update and subsequent refresh
        mock_espo_api.request.side_effect = [
            {"id": "contact123", "name": "John Updated"},  # PUT response
            {
                "id": "contact123",
                "name": "John Updated",
                "type": "Member",
            },  # GET response for refresh
        ]

        result = await crm_adapter.update_contact("contact123", update_data)

        assert result is True

        # Verify both API calls were made (PUT for update, GET for refresh)
        assert mock_espo_api.request.call_count == 2
        assert mock_espo_api.request.call_args_list[0] == (
            ("PUT", "Contact/contact123", update_data),
        )
        assert mock_espo_api.request.call_args_list[1] == (
            ("GET", "Contact/contact123"),
        )

    @pytest.mark.asyncio
    async def test_update_contact_failure(self, crm_adapter, mock_espo_api):
        """Test updating a contact with failure."""
        update_data = {"name": "John Updated"}

        # Mock failed update
        mock_espo_api.request.side_effect = EspoAPIError("Update failed")

        result = await crm_adapter.update_contact("contact123", update_data)

        assert result is False

    def test_get_cached_discord_mappings(self, crm_adapter, data_store):
        """Test getting cached Discord mappings."""
        # Create some members with Discord IDs
        john_id = data_store.create_or_update_member(
            email_508="john@508.dev",
            discord_user_id="123456789",
            display_name="John Doe",
            member_type="member",
        )
        jane_id = data_store.create_or_update_member(
            email_other="jane@example.com",
            discord_user_id="987654321",
            display_name="Jane Smith",
            member_type="candidate",
        )

        mappings = crm_adapter.get_cached_discord_mappings()

        assert len(mappings) == 2
        assert mappings["123456789"] == john_id
        assert mappings["987654321"] == jane_id

    def test_get_cache_stats(self, crm_adapter, data_store):
        """Test getting cache statistics."""
        # Add some test data
        member_id = data_store.create_or_update_member(
            email_508="john@508.dev",
            display_name="John Doe",
            member_type="member",
        )

        data_store.set_service_data(
            service="espocrm",
            entity_type="contact",
            entity_id="contact123",
            data={"id": "contact123"},
            member_id=member_id,
        )

        stats = crm_adapter.get_cache_stats()

        assert "members" in stats
        assert "service_data" in stats
        assert "cache" in stats
        assert "crm_contacts" in stats
        assert stats["members"] == 1
        assert stats["crm_contacts"] == 1

    @pytest.mark.asyncio
    async def test_load_all_members_and_candidates_api_error(
        self, crm_adapter, mock_espo_api
    ):
        """Test handling API error during initialization."""
        # Mock API error
        mock_espo_api.request.side_effect = EspoAPIError("API Error")

        # Should not raise exception, but should log error
        await crm_adapter.initialize()

        # Verify API was called
        mock_espo_api.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_contact_with_no_discord_id(self, crm_adapter):
        """Test caching a contact with no Discord ID."""
        contact_data = {
            "id": "contact999",
            "name": "No Discord User",
            "emailAddress": "nodiscord@example.com",
            "cDiscordUserID": "No Discord",  # String that should be treated as null
            "type": "Candidate",
        }

        await crm_adapter._cache_contact(contact_data)

        # Should still create member without Discord ID
        member_data = crm_adapter.data_store.get_member_by_any_email(
            "nodiscord@example.com"
        )
        assert member_data is not None
        assert member_data["member"]["discord_user_id"] is None
        assert member_data["member"]["email_other"] == "nodiscord@example.com"

    @pytest.mark.asyncio
    async def test_integration_flow(self, crm_adapter, mock_espo_api):
        """Test the complete integration flow."""
        # Mock the initialization response
        mock_espo_api.request.return_value = {
            "list": [
                {
                    "id": "contact123",
                    "name": "John Doe",
                    "c508Email": "john@508.dev",
                    "cDiscordUserID": "123456789",
                    "type": "Member",
                }
            ]
        }

        # Initialize the adapter
        await crm_adapter.initialize()

        # Verify member was loaded
        member_data = await crm_adapter.find_member_by_discord_id("123456789")
        assert member_data is not None
        assert member_data["member"]["email_508"] == "john@508.dev"

        # Test finding contact (should hit cache)
        contact = await crm_adapter.find_contact_by_discord_id("123456789")
        assert contact is not None
        assert contact["id"] == "contact123"

        # Only one API call should have been made (during initialization)
        assert mock_espo_api.request.call_count == 1
