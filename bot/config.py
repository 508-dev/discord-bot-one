"""
Configuration management for the 508.dev Discord bot.

This module uses Pydantic settings to handle environment variables
and configuration with type validation and default values.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Bot configuration settings with environment variable support.

    All settings can be overridden via environment variables.
    Required settings must be provided via environment variables or .env file.
    """
    discord_bot_token: str
    channel_id: int
    max_session_time_minutes: int = 2
    check_email_wait: int = 2
    email_username: str
    email_password: str
    imap_server: str
    smtp_server: str
    discord_sendmsg_character_limit: int = 2000

    class Config:
        env_file = ".env"


settings = Settings()