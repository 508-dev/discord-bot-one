# 508.dev Discord Bot

A Discord bot for the 508.dev co-op with multiple features.

## Overview

The 508.dev Discord bot provides convenient functionality right in Discord.

**Key capabilities:**
- **Email Integration**: Automatically forwards emails from your monitored inbox to Discord channels, keeping the team informed of important messages without constant email checking.
- **Modular Design**: New features can be added independently by different developers without conflicts.

## Project Structure

```
discord-bot-one/
├── main.py                     # Entry point - runs the bot
├── bot/
│   ├── config.py              # Configuration (Pydantic settings)
│   ├── bot.py                 # Main bot class with auto-loading
│   ├── cogs/                  # Individual bot cogs (features)
│   │   ├── email_monitor.py   # Email monitoring cog
│   │   ├── crm.py             # CRM integration cog
│   │   └── example_cog.py     # Template for new cogs
│   └── utils/                 # Shared utilities
├── pyproject.toml             # Dependencies (managed with uv)
├── .env                       # Environment variables (not in git)
├── README.md                  # This file
├── DEVELOPMENT.md             # Development setup and guidelines
└── AGENTS.md                  # AI agent development documentation
```

## Current Features

### Email Monitor ([`bot/cogs/email_monitor.py`](bot/cogs/email_monitor.py))
- Polls IMAP email inbox for new messages
- Posts new emails to designated Discord channel
- Commands: `/start-email` (start polling), `/email-status` (check status)

### CRM Integration ([`bot/cogs/crm.py`](bot/cogs/crm.py))
- Connect to EspoCRM for customer relationship management
- Search contacts and download resumes with role-based access control
- Interactive resume download buttons for easy access
- Commands: `/crm-contacts` (search contacts), `/get-resume` (download resume), `/crm-status` (API health)
- Role hierarchy: Owner > Admin > Steering Committee > Member (higher roles inherit lower role permissions)

## Quick Start (Local Development)

For local development and testing. Production deployment is handled by [Coolify](https://coolify.508.dev/).

### Setting up your own Discord Bot (for testing)

If you want to test with your own bot instead of the production bot:

1. **Create a Discord Application:**
   - Follow the [Discord Developer Quick Start Guide](https://discord.com/developers/docs/quick-start/getting-started)
   - Create a new application and bot

2. **Configure Bot Permissions:**
   - Go to your app in Discord Developer Portal → OAuth2 → URL Generator
   - Under **Scopes**, select:
     - ✅ `bot`
     - ✅ `applications.commands` (required for slash commands)
   - Under **Bot Permissions**, select:
     - ✅ `Send Messages`
     - ✅ `Use Slash Commands`
     - ✅ `Read Message History`
     - ✅ `Add Reactions`

3. **Install Bot in Your Server:**
   - Use the generated OAuth2 URL to invite the bot to your test server
   - Make sure you have admin permissions in that server

4. **Get Required Values:**
   - **Bot Token**: Discord Developer Portal → Your App → Bot → Token (keep this secret!)
   - **Channel ID**: Right-click on a Discord channel → Copy Channel ID (enable Developer Mode in Discord settings if needed)

### Local Development Setup

1. **Install uv (if not already installed):**
   ```bash
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

   # Or via pip
   pip install uv
   ```

   See [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/) for more options.

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Set up pre-commit hooks (optional but recommended):**
   ```bash
   uv run pre-commit install
   ```
   This installs git hooks that automatically run formatting and type checking before commits.

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

5. **Run the bot:**
   ```bash
   python main.py
   ```

## Environment Variables

### Required
- `DISCORD_BOT_TOKEN` - Your Discord bot token (from Discord Developer Portal)
- `CHANNEL_ID` - Discord channel ID where the bot will send messages
- `EMAIL_USERNAME` - Email account username for monitoring
- `EMAIL_PASSWORD` - Email account password (use app password for Gmail/etc.)
- `IMAP_SERVER` - IMAP server hostname (e.g., `imap.gmail.com`)
- `SMTP_SERVER` - SMTP server hostname (e.g., `smtp.gmail.com`)
- `ESPO_API_KEY` - EspoCRM API key for CRM integration
- `ESPO_BASE_URL` - EspoCRM base URL (e.g., `https://crm.508.dev`)

### Optional (with defaults)
- `CHECK_EMAIL_WAIT` - Email check interval in minutes (default: 2)
- `MAX_SESSION_TIME_MINUTES` - Max session time (default: 2)
- `DISCORD_SENDMSG_CHARACTER_LIMIT` - Message length limit (default: 2000)

## Adding New Features

The bot automatically loads all cog files from `bot/cogs/`. To add new functionality:

1. Copy the example: `cp bot/cogs/example_cog.py bot/cogs/my_cog.py`
2. Modify the class name and add your commands
3. Restart the bot - your cog loads automatically

Each feature is implemented as a Discord.py "Cog" (framework term) that can include:
- **Commands** (`@commands.command()`)
- **Event listeners** (`@commands.Cog.listener()`)  # Framework decorator
- **Background tasks** (`@tasks.loop()`)
- **Configuration** (access via `settings`)

## Architecture Benefits

- **Independent Development**: Multiple developers can work on separate features
- **Auto-loading**: New features are discovered and loaded automatically
- **Type Safety**: Pydantic settings with validation and type hints
- **Clean Separation**: Configuration, core bot logic, and features are separate
- **Easy Testing**: Individual features can be developed and tested independently

## Developing

For contributors and developers working on the bot:

📖 **[Development Guide](DEVELOPMENT.md)** - Complete setup instructions, coding guidelines, testing, and contribution workflow

📜 **[AI Agent Documentation](AGENTS.md)** - Guidelines for using AI assistants in development

🔧 **[Example Cog](bot/cogs/example_cog.py)** - Well-commented template for creating new features

## Contributing

See **[DEVELOPMENT.md](DEVELOPMENT.md)** for development setup, coding guidelines, and contribution workflow.

## Tech Stack

- **Python 3.12+**
- **discord.py** - Discord API wrapper
- **Pydantic** - Settings management and validation
- **uv** - Package management
- **IMAP/SMTP** - Email integration