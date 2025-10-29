"""
CRM-specific data adapter for EspoCRM integration.

This module provides a data layer specifically for EspoCRM operations,
reducing API calls and improving performance through caching and local storage.
"""

import logging
from typing import Any, Dict, Optional
from .data_store import ServiceDataStore
from .espo_api_client import EspoAPI, EspoAPIError

logger = logging.getLogger(__name__)


class CRMDataAdapter:
    """Data adapter for EspoCRM operations with caching and local storage."""

    def __init__(
        self, espo_api: EspoAPI, data_store: Optional[ServiceDataStore] = None
    ) -> None:
        """Initialize CRM data adapter with API client and data store backend."""
        self.espo_api = espo_api
        self.data_store = data_store or ServiceDataStore()
        self.service_name = "espocrm"

    async def initialize(self) -> None:
        """Initialize data store by loading all members and candidates from CRM."""
        logger.info("Initializing CRM data store...")
        try:
            await self._load_all_members_and_candidates()
            logger.info("CRM data store initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize CRM data store: {e}")

    async def _load_all_members_and_candidates(self) -> None:
        """Load all contacts that are members or candidates."""
        try:
            # Search for all contacts with type Member, Candidate, or Candidate / Member (legacy)
            search_params = {
                "where": [
                    {
                        "type": "or",
                        "value": [
                            {"type": "equals", "attribute": "type", "value": "Member"},
                            {
                                "type": "equals",
                                "attribute": "type",
                                "value": "Candidate",
                            },
                            {
                                "type": "equals",
                                "attribute": "type",
                                "value": "Candidate / Member",
                            },
                        ],
                    }
                ],
                "maxSize": 500,  # Adjust based on your needs
                "select": "id,name,emailAddress,c508Email,cDiscordUsername,cDiscordUserID,cGitHubUsername,type,resumeIds,resumeNames,resumeTypes",
            }

            response = self.espo_api.request("GET", "Contact", search_params)
            contacts = response.get("list", [])

            logger.info(
                f"Loading {len(contacts)} members and candidates into data store"
            )

            for contact in contacts:
                await self._cache_contact(contact)

        except EspoAPIError as e:
            logger.error(f"Failed to load members and candidates: {e}")
            raise

    async def _cache_contact(self, contact_data: Dict[str, Any]) -> None:
        """Cache a single contact's data as a member/candidate."""
        contact_id = contact_data.get("id")
        if not contact_id:
            return

        # Determine member type from CRM contact type
        crm_type = contact_data.get("type", "")
        if crm_type in ["Member", "Candidate / Member"]:
            member_type = "member"
        elif crm_type == "Candidate":
            member_type = "candidate"
        else:
            # Skip non-member/candidate contacts
            logger.debug(
                f"Skipping contact {contact_id} with type '{crm_type}' - not a member or candidate"
            )
            return

        # Extract emails
        email_508 = contact_data.get("c508Email")
        if email_508 == "None" or not email_508:
            email_508 = None

        email_other = contact_data.get("emailAddress")
        # If emailAddress is a 508.dev email, use it as email_508
        if email_other and email_other.endswith("@508.dev"):
            if not email_508:  # Only if we don't already have a c508Email
                email_508 = email_other
                email_other = None

        # Extract Discord info
        discord_user_id = contact_data.get("cDiscordUserID")
        if discord_user_id == "No Discord" or not discord_user_id:
            discord_user_id = None

        display_name = contact_data.get("name")

        # Create or update member record
        member_id = self.data_store.create_or_update_member(
            email_508=email_508,
            email_other=email_other,
            discord_user_id=discord_user_id,
            display_name=display_name,
            member_type=member_type,
        )

        # Store the CRM contact data linked to the member
        self.data_store.set_service_data(
            service=self.service_name,
            entity_type="contact",
            entity_id=contact_id,
            data=contact_data,
            member_id=member_id,
        )

    async def find_contact_by_discord_id(
        self, discord_user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Find a contact by Discord user ID, using local data first."""
        # Try local data first
        member = self.data_store.get_member_by_discord_id(discord_user_id)
        if (
            member
            and self.service_name in member["services"]
            and "contact" in member["services"][self.service_name]
        ):
            logger.debug(f"Cache hit for Discord user {discord_user_id}")
            # Return the most recent contact data
            contact_data = member["services"][self.service_name]["contact"][0]["data"]
            return contact_data if isinstance(contact_data, dict) else None

        # Cache miss - fetch from API and load member if found
        logger.debug(
            f"Cache miss for Discord user {discord_user_id}, fetching from API"
        )
        try:
            search_params = {
                "where": [
                    {
                        "type": "equals",
                        "attribute": "cDiscordUserID",
                        "value": discord_user_id,
                    }
                ],
                "maxSize": 1,
                "select": "id,name,emailAddress,c508Email,cDiscordUsername,cDiscordUserID,cGitHubUsername,type,resumeIds,resumeNames,resumeTypes",
            }

            response = self.espo_api.request("GET", "Contact", search_params)
            contacts = response.get("list", [])

            if contacts:
                contact: Dict[str, Any] = contacts[0]
                # Load this contact as a member if they're a member/candidate
                await self._cache_contact(contact)
                return contact

            return None

        except EspoAPIError as e:
            logger.error(
                f"Failed to fetch contact by Discord ID {discord_user_id}: {e}"
            )
            return None

    async def find_member_by_discord_id(
        self, discord_user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Find a member by Discord ID (optimized for cross-service usage)."""
        # This is the fast path - no CRM API calls needed
        member = self.data_store.get_member_by_discord_id(discord_user_id)
        if member:
            logger.debug(f"Found member data for Discord user {discord_user_id}")
            return member

        # Member not found locally - try to load from CRM
        logger.debug(
            f"Member not in local store, attempting CRM lookup for Discord user {discord_user_id}"
        )
        contact = await self.find_contact_by_discord_id(discord_user_id)
        if contact:
            # Contact was found and loaded as member, try again
            return self.data_store.get_member_by_discord_id(discord_user_id)

        return None

    async def find_member_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find a member by any email (optimized for cross-service usage)."""
        # Try local data first
        member = self.data_store.get_member_by_any_email(email)
        if member:
            logger.debug(f"Found member data for email {email}")
            return member

        # Member not found locally - try to load from CRM
        logger.debug(
            f"Member not in local store, attempting CRM lookup for email {email}"
        )

        # Search CRM for this email
        try:
            search_params = {
                "where": [
                    {
                        "type": "or",
                        "value": [
                            {
                                "type": "equals",
                                "attribute": "emailAddress",
                                "value": email,
                            },
                            {
                                "type": "equals",
                                "attribute": "c508Email",
                                "value": email,
                            },
                        ],
                    }
                ],
                "maxSize": 1,
                "select": "id,name,emailAddress,c508Email,cDiscordUsername,cDiscordUserID,cGitHubUsername,type,resumeIds,resumeNames,resumeTypes",
            }

            response = self.espo_api.request("GET", "Contact", search_params)
            contacts = response.get("list", [])

            if contacts:
                contact: Dict[str, Any] = contacts[0]
                # Load this contact as a member if they're a member/candidate
                await self._cache_contact(contact)
                # Try again now that it's loaded
                return self.data_store.get_member_by_any_email(email)

            return None

        except EspoAPIError as e:
            logger.error(f"Failed to fetch contact by email {email}: {e}")
            return None

    async def get_contact_by_id(
        self, contact_id: str, force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get contact by ID, using cache unless force_refresh is True."""
        if not force_refresh:
            # Try local data first
            cached = self.data_store.get_service_data(
                self.service_name, "contact", contact_id
            )
            if cached:
                logger.debug(f"Cache hit for contact {contact_id}")
                data = cached["data"]
                return data if isinstance(data, dict) else None

        # Cache miss or forced refresh - fetch from API
        logger.debug(f"Fetching contact {contact_id} from API")
        try:
            contact_data: Dict[str, Any] = self.espo_api.request(
                "GET", f"Contact/{contact_id}"
            )
            if contact_data:
                await self._cache_contact(contact_data)
                return contact_data
            return None

        except EspoAPIError as e:
            logger.error(f"Failed to fetch contact {contact_id}: {e}")
            return None

    async def search_contacts(
        self, search_params: Dict[str, Any], cache_ttl: int = 300
    ) -> Dict[str, Any]:
        """Search contacts with caching for repeated searches."""
        # Create cache key from search params
        import hashlib
        import json

        cache_key = (
            "search:"
            + hashlib.md5(
                json.dumps(search_params, sort_keys=True).encode()
            ).hexdigest()
        )

        # Try cache first
        cached_result = self.data_store.get_cache(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for search: {cache_key}")
            if isinstance(cached_result, dict):
                return cached_result
            # Fall through to API call if cached result is not a dict

        # Cache miss - fetch from API
        logger.debug("Cache miss for search, fetching from API")
        try:
            response: Dict[str, Any] = self.espo_api.request(
                "GET", "Contact", search_params
            )

            # Cache the search results
            self.data_store.set_cache(cache_key, response, self.service_name, cache_ttl)

            # Also cache individual contacts from the results
            contacts = response.get("list", [])
            for contact in contacts:
                await self._cache_contact(contact)

            return response

        except EspoAPIError as e:
            logger.error(f"Failed to search contacts: {e}")
            raise

    async def update_contact(
        self, contact_id: str, update_data: Dict[str, Any]
    ) -> bool:
        """Update a contact and refresh cache."""
        try:
            response = self.espo_api.request(
                "PUT", f"Contact/{contact_id}", update_data
            )
            if response:
                # Refresh the contact in cache
                await self.get_contact_by_id(contact_id, force_refresh=True)
                return True
            return False

        except EspoAPIError as e:
            logger.error(f"Failed to update contact {contact_id}: {e}")
            return False

    async def invalidate_contact(self, contact_id: str) -> None:
        """Remove a contact from cache."""
        # Note: We don't delete from cache, we just force refresh next time
        # This is safer and handles the case where the contact was updated elsewhere
        logger.debug(f"Marking contact {contact_id} for refresh")

    def get_cached_discord_mappings(self) -> Dict[str, str]:
        """Get all cached Discord user ID to email mappings."""
        return self.data_store.get_discord_user_mappings()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = self.data_store.get_stats()
        # Add CRM-specific stats
        crm_contacts = len(
            [data for data in self.data_store.get_all_service_data(self.service_name)]
        )
        stats["crm_contacts"] = crm_contacts
        return stats

    def clear_cache(self) -> int:
        """Clear all CRM cache entries."""
        return self.data_store.clear_service_cache(self.service_name)
