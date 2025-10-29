"""
Unified data store for multiple external services.

This module provides a SQLite-based data store with JSON storage for flexible
data management across services like EspoCRM, Kimai, Migadu, etc.
Includes both persistent service data and temporary caching capabilities.
"""

import sqlite3
import json
import time
from typing import Any, Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ServiceDataStore:
    """Unified data store for multiple external services."""

    def __init__(self, db_path: str = "data/service_data.db") -> None:
        """Initialize the data store with SQLite database."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")

            # 508.dev members and candidates (core people we track across services)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS members (
                    id TEXT PRIMARY KEY,               -- UUID or auto-increment
                    email_508 TEXT UNIQUE,             -- john@508.dev (only for members)
                    email_other TEXT,                  -- john@gmail.com (for candidates)
                    discord_user_id TEXT UNIQUE,       -- Discord linking
                    display_name TEXT,                  -- Preferred name
                    member_type TEXT CHECK(member_type IN ('candidate', 'member')) NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

            # All service data (people, projects, teams, external contacts, etc.)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS service_data (
                    id TEXT PRIMARY KEY,               -- "espocrm:contact:123", "kimai:project:456"
                    service TEXT NOT NULL,             -- "espocrm", "kimai", "migadu", etc.
                    entity_type TEXT NOT NULL,         -- "contact", "project", "team", "timesheet"
                    entity_id TEXT NOT NULL,           -- Service's internal ID
                    member_id TEXT,                     -- Links to members table (nullable)
                    data JSON NOT NULL,                -- Full service-specific data
                    updated_at REAL NOT NULL,
                    FOREIGN KEY(member_id) REFERENCES members(id)
                )
            """)

            # Cache for API responses, search results, auth codes, etc.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value JSON NOT NULL,
                    expires_at REAL,
                    service TEXT NOT NULL
                )
            """)

            # Create indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_members_email_508
                ON members(email_508) WHERE email_508 IS NOT NULL
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_members_discord
                ON members(discord_user_id) WHERE discord_user_id IS NOT NULL
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_service_data_service
                ON service_data(service)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_service_data_member
                ON service_data(member_id) WHERE member_id IS NOT NULL
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_service_data_service_type
                ON service_data(service, entity_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_service_data_service_entity
                ON service_data(service, entity_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_service
                ON cache(service)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_expires
                ON cache(expires_at) WHERE expires_at IS NOT NULL
            """)

            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with JSON support."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def get_member_by_discord_id(
        self, discord_user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get complete member data by Discord user ID."""
        with self._get_connection() as conn:
            # Get member
            member_row = conn.execute(
                "SELECT * FROM members WHERE discord_user_id = ?", (discord_user_id,)
            ).fetchone()

            if not member_row:
                return None

            member = dict(member_row)
            member_id = member["id"]

            # Get all service data for this member
            service_rows = conn.execute(
                "SELECT * FROM service_data WHERE member_id = ?", (member_id,)
            ).fetchall()

            result = {"member": member, "services": {}}
            for row in service_rows:
                service = row["service"]
                entity_type = row["entity_type"]

                if service not in result["services"]:
                    result["services"][service] = {}
                if entity_type not in result["services"][service]:
                    result["services"][service][entity_type] = []

                service_data = dict(row)
                service_data["data"] = json.loads(service_data["data"])
                result["services"][service][entity_type].append(service_data)

            return result

    def get_member_by_email_508(self, email_508: str) -> Optional[Dict[str, Any]]:
        """Get complete member data by 508.dev email."""
        with self._get_connection() as conn:
            # Get member
            member_row = conn.execute(
                "SELECT * FROM members WHERE email_508 = ?", (email_508,)
            ).fetchone()

            if not member_row:
                return None

            member = dict(member_row)
            member_id = member["id"]

            # Get all service data for this member
            service_rows = conn.execute(
                "SELECT * FROM service_data WHERE member_id = ?", (member_id,)
            ).fetchall()

            result = {"member": member, "services": {}}
            for row in service_rows:
                service = row["service"]
                entity_type = row["entity_type"]

                if service not in result["services"]:
                    result["services"][service] = {}
                if entity_type not in result["services"][service]:
                    result["services"][service][entity_type] = []

                service_data = dict(row)
                service_data["data"] = json.loads(service_data["data"])
                result["services"][service][entity_type].append(service_data)

            return result

    def get_member_by_any_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get member by either 508 email or other email."""
        # Try 508 email first
        result = self.get_member_by_email_508(email)
        if result:
            return result

        # Try other email
        with self._get_connection() as conn:
            member_row = conn.execute(
                "SELECT * FROM members WHERE email_other = ?", (email,)
            ).fetchone()

            if not member_row:
                return None

            member = dict(member_row)
            member_id = member["id"]

            # Get all service data for this member
            service_rows = conn.execute(
                "SELECT * FROM service_data WHERE member_id = ?", (member_id,)
            ).fetchall()

            result = {"member": member, "services": {}}
            for row in service_rows:
                service = row["service"]
                entity_type = row["entity_type"]

                if service not in result["services"]:
                    result["services"][service] = {}
                if entity_type not in result["services"][service]:
                    result["services"][service][entity_type] = []

                service_data = dict(row)
                service_data["data"] = json.loads(service_data["data"])
                result["services"][service][entity_type].append(service_data)

            return result

    def create_or_update_member(
        self,
        member_id: Optional[str] = None,
        email_508: Optional[str] = None,
        email_other: Optional[str] = None,
        discord_user_id: Optional[str] = None,
        display_name: Optional[str] = None,
        member_type: Optional[str] = None,
    ) -> str:
        """Create or update a member. Returns member ID."""
        import uuid

        now = time.time()

        with self._get_connection() as conn:
            if member_id:
                # Update existing member
                existing = conn.execute(
                    "SELECT id FROM members WHERE id = ?", (member_id,)
                ).fetchone()

                if existing:
                    updates = []
                    params: list[Any] = []

                    if email_508 is not None:
                        updates.append("email_508 = ?")
                        params.append(email_508)
                    if email_other is not None:
                        updates.append("email_other = ?")
                        params.append(email_other)
                    if discord_user_id is not None:
                        updates.append("discord_user_id = ?")
                        params.append(discord_user_id)
                    if display_name is not None:
                        updates.append("display_name = ?")
                        params.append(display_name)
                    if member_type is not None:
                        updates.append("member_type = ?")
                        params.append(member_type)

                    if updates:
                        updates.append("updated_at = ?")
                        params.append(now)
                        params.append(member_id)

                        conn.execute(
                            f"UPDATE members SET {', '.join(updates)} WHERE id = ?",
                            params,
                        )
                    conn.commit()
                    return member_id

            # Create new member or member_id not found
            if not member_id:
                member_id = str(uuid.uuid4())

            # Validate member_type
            if member_type not in ["candidate", "member"]:
                raise ValueError("member_type must be 'candidate' or 'member'")

            conn.execute(
                """
                INSERT OR REPLACE INTO members
                (id, email_508, email_other, discord_user_id, display_name, member_type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    member_id,
                    email_508,
                    email_other,
                    discord_user_id,
                    display_name,
                    member_type,
                    now,
                    now,
                ),
            )

            conn.commit()
            return member_id

    def set_service_data(
        self,
        service: str,
        entity_type: str,
        entity_id: str,
        data: Dict[str, Any],
        member_id: Optional[str] = None,
    ) -> None:
        """Store or update service-specific data."""
        now = time.time()
        service_data_id = f"{service}:{entity_type}:{entity_id}"

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO service_data
                (id, service, entity_type, entity_id, member_id, data, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    service_data_id,
                    service,
                    entity_type,
                    entity_id,
                    member_id,
                    json.dumps(data),
                    now,
                ),
            )
            conn.commit()

    def get_service_data(
        self, service: str, entity_type: str, entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get specific service data by service, entity type, and entity ID."""
        service_data_id = f"{service}:{entity_type}:{entity_id}"

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM service_data WHERE id = ?", (service_data_id,)
            ).fetchone()

            if row:
                result = dict(row)
                result["data"] = json.loads(result["data"])
                return result
            return None

    def get_service_data_by_legacy_id(
        self, service: str, entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get service data by legacy service:entity_id format (for compatibility)."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM service_data WHERE service = ? AND entity_id = ?",
                (service, entity_id),
            ).fetchone()

            if row:
                result = dict(row)
                result["data"] = json.loads(result["data"])
                return result
            return None

    def get_all_service_data(self, service: str) -> List[Dict[str, Any]]:
        """Get all data for a specific service."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM service_data WHERE service = ? ORDER BY updated_at DESC",
                (service,),
            ).fetchall()

            result = []
            for row in rows:
                service_data = dict(row)
                service_data["data"] = json.loads(service_data["data"])
                result.append(service_data)

            return result

    def set_cache(
        self, key: str, value: Any, service: str, ttl_seconds: Optional[int] = None
    ) -> None:
        """Set a cache value with optional TTL."""
        expires_at = None
        if ttl_seconds:
            expires_at = time.time() + ttl_seconds

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache (key, value, expires_at, service)
                VALUES (?, ?, ?, ?)
            """,
                (key, json.dumps(value), expires_at, service),
            )
            conn.commit()

    def get_cache(self, key: str) -> Optional[Any]:
        """Get a cache value, checking expiry."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
            ).fetchone()

            if not row:
                return None

            expires_at = row["expires_at"]
            if expires_at and time.time() > expires_at:
                # Expired, delete it
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
                return None

            return json.loads(row["value"])

    def clear_expired_cache(self) -> int:
        """Clear all expired cache entries. Returns number of deleted entries."""
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (now,),
            )
            deleted = cursor.rowcount
            conn.commit()
            return deleted

    def get_discord_user_mappings(self) -> Dict[str, str]:
        """Get all Discord user ID to member ID mappings."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT discord_user_id, id
                FROM members
                WHERE discord_user_id IS NOT NULL
            """).fetchall()

            return {row["discord_user_id"]: row["id"] for row in rows}

    def get_all_members(self) -> List[Dict[str, Any]]:
        """Get all members."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM members ORDER BY created_at DESC
            """).fetchall()

            return [dict(row) for row in rows]

    def clear_service_cache(self, service: str) -> int:
        """Clear all cache entries for a specific service."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM cache WHERE service = ?", (service,))
            deleted = cursor.rowcount
            conn.commit()
            return deleted

    def get_stats(self) -> Dict[str, Any]:
        """Get data store statistics."""
        with self._get_connection() as conn:
            stats = {}

            # Member count
            stats["members"] = conn.execute(
                "SELECT COUNT(*) as count FROM members"
            ).fetchone()["count"]

            # Service data counts
            service_counts = conn.execute("""
                SELECT service, COUNT(*) as count
                FROM service_data
                GROUP BY service
            """).fetchall()
            stats["service_data"] = {
                row["service"]: row["count"] for row in service_counts
            }

            # Cache counts
            cache_counts = conn.execute("""
                SELECT service, COUNT(*) as count
                FROM cache
                GROUP BY service
            """).fetchall()
            stats["cache"] = {row["service"]: row["count"] for row in cache_counts}

            # Expired cache count
            now = time.time()
            expired_count = conn.execute(
                """
                SELECT COUNT(*) as count
                FROM cache
                WHERE expires_at IS NOT NULL AND expires_at <= ?
            """,
                (now,),
            ).fetchone()["count"]
            stats["expired_cache"] = expired_count

            return stats
