"""
Configuration management for the 508.dev Discord bot.

This module uses Pydantic settings to handle environment variables
and configuration with type validation and default values.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Bot configuration settings with environment variable support.

    All settings can be overridden via environment variables.
    Required settings must be provided via environment variables or .env file.
    """

    discord_bot_token: str

    discord_sendmsg_character_limit: int = 2000

    # Healthcheck Configuration
    healthcheck_port: int = 3000

    # Email Monitoring Configuration
    channel_id: int
    check_email_wait: int = 2
    email_username: str
    email_password: str
    imap_server: str
    smtp_server: str

    # CRM/EspoCRM settings
    espo_api_key: str
    espo_base_url: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()  # type: ignore[call-arg]
