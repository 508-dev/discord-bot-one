"""
Kimai API client for time tracking integration.

This module provides a client for interacting with the Kimai time tracking API.
"""

import requests
from typing import Any, Dict, List
from datetime import datetime


class KimaiAPIError(Exception):
    """An exception class for Kimai API errors"""


class KimaiAPI:
    """Client for interacting with the Kimai time tracking API."""

    def __init__(self, base_url: str, api_token: str) -> None:
        """
        Initialize the Kimai API client.

        Args:
            base_url: Base URL of the Kimai instance (e.g., https://kimai.example.com)
            api_token: API token for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.status_code: int | None = None

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with authentication."""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def _normalize_url(self, endpoint: str) -> str:
        """Normalize API endpoint URL."""
        endpoint = endpoint.lstrip("/")
        return f"{self.base_url}/api/{endpoint}"

    def _request(
        self, method: str, endpoint: str, params: Dict[str, Any] | None = None
    ) -> Any:
        """
        Make an HTTP request to the Kimai API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., 'timesheets')
            params: Query parameters or JSON body

        Returns:
            API response data (list or dict)

        Raises:
            KimaiAPIError: If the request fails
        """
        if params is None:
            params = {}

        url = self._normalize_url(endpoint)
        headers = self._get_headers()

        try:
            if method in ["POST", "PATCH", "PUT"]:
                response = requests.request(method, url, headers=headers, json=params)
            else:
                response = requests.request(method, url, headers=headers, params=params)

            self.status_code = response.status_code

            if self.status_code not in [200, 201]:
                error_msg = f"API request failed with status {self.status_code}"
                try:
                    error_data = response.json()
                    if "message" in error_data:
                        error_msg += f": {error_data['message']}"
                except Exception:
                    error_msg += f": {response.text}"
                raise KimaiAPIError(error_msg)

            if not response.content:
                return []

            return response.json()

        except requests.RequestException as e:
            raise KimaiAPIError(f"HTTP request failed: {str(e)}")

    def get_projects(self) -> List[Dict[str, Any]]:
        """
        Get all projects from Kimai.

        Returns:
            List of project dictionaries
        """
        return self._request("GET", "projects")  # type: ignore[return-value]

    def get_project_by_name(self, project_name: str) -> Dict[str, Any] | None:
        """
        Find a project by name (case-insensitive search).

        Args:
            project_name: Name of the project to search for

        Returns:
            Project dictionary if found, None otherwise
        """
        projects = self.get_projects()
        project_name_lower = project_name.lower()

        for project in projects:
            if project.get("name", "").lower() == project_name_lower:
                return project

        return None

    def get_timesheets(
        self,
        project_id: int | None = None,
        begin: datetime | None = None,
        end: datetime | None = None,
        user_id: int | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Get timesheet entries with optional filters.

        Args:
            project_id: Filter by project ID
            begin: Start date/time for filtering
            end: End date/time for filtering
            user_id: Filter by user ID

        Returns:
            List of timesheet entry dictionaries
        """
        params: Dict[str, Any] = {}

        if project_id is not None:
            params["project"] = project_id

        if begin is not None:
            params["begin"] = begin.strftime("%Y-%m-%dT%H:%M:%S")

        if end is not None:
            params["end"] = end.strftime("%Y-%m-%dT%H:%M:%S")

        if user_id is not None:
            params["user"] = user_id

        return self._request("GET", "timesheets", params)  # type: ignore[return-value]

    def get_users(self) -> List[Dict[str, Any]]:
        """
        Get all users from Kimai.

        Returns:
            List of user dictionaries
        """
        return self._request("GET", "users")  # type: ignore[return-value]

    def get_project_hours_by_user(
        self,
        project_id: int,
        begin: datetime | None = None,
        end: datetime | None = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get total hours logged for a project, broken down by user.

        Args:
            project_id: ID of the project
            begin: Start date/time for filtering
            end: End date/time for filtering

        Returns:
            Dictionary mapping user names to their hours and details:
            {
                "User Name": {
                    "hours": 12.5,
                    "duration_seconds": 45000,
                    "entries": 5
                }
            }
        """
        timesheets = self.get_timesheets(project_id=project_id, begin=begin, end=end)
        users = self.get_users()

        # Create user ID to name mapping
        user_map = {user["id"]: user.get("alias", user.get("username", "Unknown")) for user in users}

        # Aggregate hours by user
        user_hours: Dict[str, Dict[str, Any]] = {}

        for entry in timesheets:
            user_id = entry.get("user")
            duration = entry.get("duration", 0)  # Duration in seconds

            if user_id is None:
                continue

            user_name = user_map.get(user_id, f"User {user_id}")

            if user_name not in user_hours:
                user_hours[user_name] = {
                    "hours": 0.0,
                    "duration_seconds": 0,
                    "entries": 0,
                }

            user_hours[user_name]["duration_seconds"] += duration
            user_hours[user_name]["hours"] = user_hours[user_name]["duration_seconds"] / 3600
            user_hours[user_name]["entries"] += 1

        return user_hours
