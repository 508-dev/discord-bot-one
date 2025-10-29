"""
Tests for the unified service data store.
"""

import pytest
import tempfile
import time
from pathlib import Path

from bot.utils.data_store import ServiceDataStore


class TestServiceDataStore:
    """Test cases for the ServiceDataStore class."""

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

    def test_initialization(self, temp_db):
        """Test that data store initializes correctly."""
        data_store = ServiceDataStore(temp_db)
        assert Path(temp_db).exists()

        # Check that tables were created
        with data_store._get_connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [row["name"] for row in tables]

            assert "members" in table_names
            assert "service_data" in table_names
            assert "cache" in table_names

    def test_create_member_new(self, data_store):
        """Test creating a new member."""
        email = "john@508.dev"
        discord_id = "123456789"
        name = "John Doe"

        data_store.create_or_update_member(
            email_508=email,
            discord_user_id=discord_id,
            display_name=name,
            member_type="member",
        )

        # Verify member was created
        with data_store._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM members WHERE email_508 = ?", (email,)
            ).fetchone()

            assert row is not None
            assert row["email_508"] == email
            assert row["discord_user_id"] == discord_id
            assert row["display_name"] == name
            assert row["member_type"] == "member"
            assert row["created_at"] > 0
            assert row["updated_at"] > 0

    def test_update_member_existing(self, data_store):
        """Test updating an existing member."""
        email = "john@508.dev"

        # Create initial member
        member_id = data_store.create_or_update_member(
            email_508=email,
            discord_user_id="123456789",
            display_name="John Doe",
            member_type="member",
        )

        # Update member
        time.sleep(0.01)  # Ensure different timestamp
        data_store.create_or_update_member(
            member_id=member_id, discord_user_id="987654321", display_name="John Smith"
        )

        # Verify member was updated
        with data_store._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM members WHERE email_508 = ?", (email,)
            ).fetchone()

            assert row["discord_user_id"] == "987654321"
            assert row["display_name"] == "John Smith"
            assert row["updated_at"] > row["created_at"]

    def test_set_and_get_service_data(self, data_store):
        """Test storing and retrieving service data."""
        service = "espocrm"
        entity_id = "contact123"
        email = "john@508.dev"
        contact_data = {
            "id": entity_id,
            "name": "John Doe",
            "email": "john@example.com",
            "github": "johndoe",
        }

        # Create the member first to satisfy foreign key constraint
        member_id = data_store.create_or_update_member(
            email_508=email, display_name="John Doe", member_type="member"
        )

        data_store.set_service_data(
            service=service,
            entity_type="contact",
            entity_id=entity_id,
            data=contact_data,
            member_id=member_id,
        )

        # Retrieve service data
        result = data_store.get_service_data(service, "contact", entity_id)

        assert result is not None
        assert result["service"] == service
        assert result["entity_type"] == "contact"
        assert result["entity_id"] == entity_id
        assert result["member_id"] == member_id
        assert result["data"] == contact_data
        assert result["updated_at"] > 0

    def test_get_service_data_not_found(self, data_store):
        """Test retrieving non-existent service data."""
        result = data_store.get_service_data("espocrm", "contact", "nonexistent")
        assert result is None

    def test_get_all_service_data(self, data_store):
        """Test retrieving all data for a service."""
        service = "espocrm"

        # Add multiple contacts
        for i in range(3):
            email = f"contact{i}@508.dev"
            # Create member first
            member_id = data_store.create_or_update_member(
                email_508=email, display_name=f"Contact {i}", member_type="member"
            )
            data_store.set_service_data(
                service=service,
                entity_type="contact",
                entity_id=f"contact{i}",
                data={"id": f"contact{i}", "name": f"Contact {i}"},
                member_id=member_id,
            )

        # Add data for different service
        john_email = "john@508.dev"
        john_member_id = data_store.create_or_update_member(
            email_508=john_email, display_name="John Doe", member_type="member"
        )
        data_store.set_service_data(
            service="kimai",
            entity_type="project",
            entity_id="project1",
            data={"id": "project1", "name": "Project 1"},
            member_id=john_member_id,
        )

        # Get all espocrm data
        results = data_store.get_all_service_data(service)

        assert len(results) == 3
        for result in results:
            assert result["service"] == service
            assert result["entity_type"] == "contact"
            assert result["entity_id"].startswith("contact")

    def test_get_member_by_discord_id(self, data_store):
        """Test retrieving complete member data by Discord ID."""
        email = "john@508.dev"
        discord_id = "123456789"

        # Create member
        member_id = data_store.create_or_update_member(
            email_508=email,
            discord_user_id=discord_id,
            display_name="John Doe",
            member_type="member",
        )

        # Add service data
        data_store.set_service_data(
            service="espocrm",
            entity_type="contact",
            entity_id="contact123",
            data={"id": "contact123", "name": "John Doe"},
            member_id=member_id,
        )

        # Retrieve member
        member_data = data_store.get_member_by_discord_id(discord_id)

        assert member_data is not None
        assert member_data["member"]["email_508"] == email
        assert member_data["member"]["discord_user_id"] == discord_id
        assert "espocrm" in member_data["services"]
        assert "contact" in member_data["services"]["espocrm"]
        assert len(member_data["services"]["espocrm"]["contact"]) == 1
        assert (
            member_data["services"]["espocrm"]["contact"][0]["data"]["id"]
            == "contact123"
        )

    def test_get_member_by_discord_id_not_found(self, data_store):
        """Test retrieving member with non-existent Discord ID."""
        member_data = data_store.get_member_by_discord_id("nonexistent")
        assert member_data is None

    def test_get_member_by_email(self, data_store):
        """Test retrieving complete member data by email."""
        email = "john@508.dev"
        discord_id = "123456789"

        # Create member
        member_id = data_store.create_or_update_member(
            email_508=email,
            discord_user_id=discord_id,
            display_name="John Doe",
            member_type="member",
        )

        # Add service data
        data_store.set_service_data(
            service="espocrm",
            entity_type="contact",
            entity_id="contact123",
            data={"id": "contact123", "name": "John Doe"},
            member_id=member_id,
        )

        # Retrieve member
        member_data = data_store.get_member_by_email_508(email)

        assert member_data is not None
        assert member_data["member"]["email_508"] == email
        assert member_data["member"]["discord_user_id"] == discord_id
        assert "espocrm" in member_data["services"]

    def test_cache_operations(self, data_store):
        """Test cache set/get operations."""
        key = "test:key"
        value = {"test": "data", "number": 42}
        service = "test_service"

        # Set cache without TTL
        data_store.set_cache(key, value, service)

        # Get cache
        result = data_store.get_cache(key)
        assert result == value

    def test_cache_with_ttl(self, data_store):
        """Test cache with TTL expiration."""
        key = "test:ttl"
        value = {"test": "data"}
        service = "test_service"

        # Set cache with very short TTL
        data_store.set_cache(key, value, service, ttl_seconds=1)

        # Should be available immediately
        result = data_store.get_cache(key)
        assert result == value

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired and return None
        result = data_store.get_cache(key)
        assert result is None

    def test_cache_not_found(self, data_store):
        """Test retrieving non-existent cache key."""
        result = data_store.get_cache("nonexistent:key")
        assert result is None

    def test_clear_expired_cache(self, data_store):
        """Test clearing expired cache entries."""
        # Add some cache entries
        data_store.set_cache("key1", {"data": 1}, "service1", ttl_seconds=1)
        data_store.set_cache("key2", {"data": 2}, "service1")  # No TTL
        data_store.set_cache("key3", {"data": 3}, "service1", ttl_seconds=1)

        # Wait for expiration
        time.sleep(1.1)

        # Clear expired entries
        deleted_count = data_store.clear_expired_cache()
        assert deleted_count == 2

        # Non-expired entry should still exist
        result = data_store.get_cache("key2")
        assert result == {"data": 2}

    def test_clear_service_cache(self, data_store):
        """Test clearing cache entries for a specific service."""
        # Add cache entries for different services
        data_store.set_cache("key1", {"data": 1}, "service1")
        data_store.set_cache("key2", {"data": 2}, "service1")
        data_store.set_cache("key3", {"data": 3}, "service2")

        # Clear service1 cache
        deleted_count = data_store.clear_service_cache("service1")
        assert deleted_count == 2

        # service1 entries should be gone
        assert data_store.get_cache("key1") is None
        assert data_store.get_cache("key2") is None

        # service2 entry should remain
        assert data_store.get_cache("key3") == {"data": 3}

    def test_get_discord_user_mappings(self, data_store):
        """Test retrieving Discord user ID to member ID mappings."""
        # Create members with Discord IDs
        john_id = data_store.create_or_update_member(
            email_508="john@508.dev",
            discord_user_id="123456789",
            display_name="John Doe",
            member_type="member",
        )
        jane_id = data_store.create_or_update_member(
            email_508="jane@508.dev",
            discord_user_id="987654321",
            display_name="Jane Smith",
            member_type="member",
        )
        # Create member without Discord ID
        bob_id = data_store.create_or_update_member(
            email_508="bob@508.dev", display_name="Bob Johnson", member_type="member"
        )

        mappings = data_store.get_discord_user_mappings()

        assert len(mappings) == 2
        assert mappings["123456789"] == john_id
        assert mappings["987654321"] == jane_id
        assert bob_id not in mappings.values()

    def test_get_stats(self, data_store):
        """Test retrieving data store statistics."""
        # Add some test data
        member_id = data_store.create_or_update_member(
            email_508="john@508.dev",
            discord_user_id="123456789",
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

        data_store.set_cache("key1", {"data": 1}, "espocrm")
        data_store.set_cache("key2", {"data": 2}, "espocrm", ttl_seconds=1)

        # Wait for one cache entry to expire
        time.sleep(1.1)

        stats = data_store.get_stats()

        assert stats["members"] == 1
        assert stats["service_data"]["espocrm"] == 1
        assert stats["cache"]["espocrm"] == 2
        assert stats["expired_cache"] == 1

    def test_foreign_key_constraint(self, data_store):
        """Test that foreign key constraints work correctly."""
        # Try to add service data with null member_id
        # This should work since member_id is nullable
        data_store.set_service_data(
            service="espocrm",
            entity_type="contact",
            entity_id="contact123",
            data={"id": "contact123"},
            member_id=None,
        )

        # Verify it was stored
        result = data_store.get_service_data("espocrm", "contact", "contact123")
        assert result is not None
        assert result["member_id"] is None

    def test_json_serialization(self, data_store):
        """Test that complex JSON data is handled correctly."""
        complex_data = {
            "string": "value",
            "number": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "nested": {"key": "value", "array": ["a", "b", "c"]},
        }

        data_store.set_service_data(
            service="espocrm",
            entity_type="contact",
            entity_id="complex",
            data=complex_data,
        )

        result = data_store.get_service_data("espocrm", "contact", "complex")
        assert result["data"] == complex_data

    def test_concurrent_access(self, data_store):
        """Test that concurrent access doesn't cause issues."""
        import threading
        import time

        results = []
        errors = []

        def worker(worker_id):
            try:
                for i in range(10):
                    email = f"worker{worker_id}@508.dev"
                    data_store.create_or_update_member(
                        email_508=email,
                        discord_user_id=f"{worker_id}{i:03d}",
                        display_name=f"Worker {worker_id}",
                        member_type="member",
                    )
                    time.sleep(0.001)  # Small delay
                results.append(f"worker{worker_id}_success")
            except Exception as e:
                errors.append(f"worker{worker_id}_error: {e}")

        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 3

        # Verify all members were created
        stats = data_store.get_stats()
        assert stats["members"] == 3
