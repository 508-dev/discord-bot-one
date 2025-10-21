# Development Guide

This guide covers environment setup, development workflow, and contribution guidelines for the 508.dev Discord bot.

## Environment Setup

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

1. **Clone the repository:**
   ```bash
   git clone git@github.com:508-dev/discord-bot-one.git
   cd discord-bot-one
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your configuration:
   ```bash
   DISCORD_BOT_TOKEN=your_bot_token_here
   EMAIL_USERNAME=your_email@example.com
   EMAIL_PASSWORD=your_app_password
   CHANNEL_ID=1391742724666822798
   ```

### Discord Bot Setup

1. **Create a Discord Application:**
   - Go to https://discord.com/developers/applications
   - Click "New Application"
   - Give it a name (e.g., "508.dev Bot")

2. **Create a Bot:**
   - Go to "Bot" tab in your application
   - Click "Add Bot"
   - Copy the token for use in environment variables

3. **Set Bot Permissions:**
   - In "Bot" tab, enable these Privileged Gateway Intents:
     - Message Content Intent
     - Server Members Intent
   - In "OAuth2 > URL Generator":
     - Select "bot" scope
     - Select permissions: Send Messages, Read Message History, etc.

4. **Invite Bot to Server:**
   - Use the generated URL to invite your bot
   - Make sure it has permissions in your target channel

### Email Setup (for email monitoring feature)

The bot can monitor an email inbox and post new messages to Discord.

1. **Email Provider Setup:**
   - Use an email provider with IMAP access (Gmail, ProtonMail, etc.)
   - Generate an app-specific password (not your regular password)

2. **Required Environment Variables:**
   ```bash
   EMAIL_USERNAME=your-email@domain.com
   EMAIL_PASSWORD=your-app-password
   IMAP_SERVER=imap.domain.com  # Default: imap.migadu.com
   SMTP_SERVER=smtp.domain.com  # Default: smtp.migadu.com
   ```

## Development Workflow

### Running the Bot

```bash
# Development mode
python main.py

# With debug logging
PYTHONPATH=. python -m bot.main --debug
```

### Testing Features

1. **Start the bot locally**
2. **Test commands in Discord:**
   ```
   !hello
   !ping
   !info
   !st      # Start email monitoring
   !is_running  # Check email monitoring status
   ```

### Adding Dependencies

```bash
# Add a new package
uv add requests

# Add development dependency
uv add --dev pytest

# Update all dependencies
uv sync --upgrade
```

## Adding New Features

### 1. Create a New Feature

Each new feature should be implemented as a Discord.py "Cog" (the underlying framework still uses this term). Copy `bot/features/example_feature.py` as a starting point:

```bash
cp bot/features/example_feature.py bot/features/my_new_feature.py
```

### 2. Feature Structure

A basic feature follows this pattern:

```python
from discord.ext import commands
import discord
from bot.config import settings

class MyFeature(commands.Cog  # Discord.py framework term):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="mycommand")
    async def my_command(self, ctx):
        """Command description"""
        await ctx.send("Hello world!")

    @commands.Cog  # Discord.py framework term.listener()
    async def on_message(self, message):
        """Event listener example"""
        # React to messages
        pass

async def setup(bot):
    await bot.add_cog  # Discord.py framework method(MyFeature(bot))
```

### 3. Available Resources

- **Configuration**: Import settings from `bot.config.settings`
- **Bot instance**: Access via `self.bot` in feature methods
- **Channel access**: Use `self.bot.get_channel(settings.channel_id)`
- **Database**: Add database utilities to `bot/utils/` if needed

### 4. Commands and Events

- **Commands**: Use `@commands.command()` decorator
- **Event listeners**: Use `@commands.Cog  # Discord.py framework term.listener()` decorator
- **Background tasks**: Use `@tasks.loop()` from discord.ext.tasks

### 5. Testing Your Feature

The bot automatically loads all features from the `bot/features/` directory. Simply:

1. Add your new feature file to `bot/features/`
2. Restart the bot
3. Your commands will be available immediately

### 6. Configuration

Add new configuration variables to `bot/config.py`:

```python
class Settings(BaseSettings):
    # Existing settings...
    my_new_setting: str = "default_value"
    my_required_setting: str  # Will require env var
```

Then set environment variables in `.env`:
```
MY_REQUIRED_SETTING=some_value
```

## Code Quality

### Style Guidelines
- Follow existing code patterns in the project
- Use type hints where possible: `async def command(self, ctx: commands.Context)`
- Add docstrings to all commands and functions
- Keep features focused on single areas of functionality
- Use meaningful variable and function names

### Error Handling
```python
@commands.command()
async def safe_command(self, ctx):
    try:
        # Your command logic here
        result = some_operation()
        await ctx.send(f"Success: {result}")
    except SpecificException as e:
        await ctx.send(f"Expected error: {e}")
        print(f"Command {ctx.command} error: {e}")
    except Exception as e:
        await ctx.send("An unexpected error occurred")
        print(f"Unexpected error in {ctx.command}: {e}")
```

### Testing
- Test all commands manually in Discord
- Test error conditions (missing arguments, invalid input)
- Test with different user permissions
- Verify background tasks start/stop correctly

## Git Workflow

### Branch Strategy
```bash
# Create feature branch
git checkout -b feature/my-new-feature

# Make changes, commit frequently
git add .
git commit -m "Add new feature command"

# Push and create PR
git push origin feature/my-new-feature
```

### Commit Messages
- Use clear, descriptive commit messages
- Start with verb: "Add", "Fix", "Update", "Remove"
- Examples:
  - `Add weather command to utility feature`
  - `Fix email parsing for HTML messages`
  - `Update Discord.py to v2.3.2`

## Testing

### Running Tests Locally

```bash
# Install dev dependencies
uv sync --all-extras

# Run all tests
uv run pytest

# Run with coverage
uv run coverage run -m pytest
uv run coverage report

# Run specific test file
uv run pytest tests/unit/test_config.py -v

# Run tests with output
uv run pytest -s -v
```

### Test Structure
- `tests/unit/` - Unit tests for individual components
- `tests/integration/` - Integration tests for feature interactions
- `tests/conftest.py` - Shared test fixtures and configuration

### CI/CD

Tests run automatically on:
- Pull requests to main branch
- Pushes to main branch

The GitHub Actions workflow runs:
- **Tests**: Multiple Python versions (3.8-3.12)
- **Linting**: Code style with ruff and type checking with mypy
- **Security**: Bandit security linting and safety dependency checks

## Deployment

### Coolify Deployment

This bot is deployed using [Coolify](https://coolify.io/) which handles:
- Environment variable management
- Automatic deployments from git
- Process monitoring and restarts
- Log aggregation

### Environment Variables in Coolify

Set these environment variables in your Coolify application:

**Required:**
- `DISCORD_BOT_TOKEN` - Your Discord bot token
- `EMAIL_USERNAME` - Email account username
- `EMAIL_PASSWORD` - Email account app password

**Optional (with defaults):**
- `CHANNEL_ID` - Discord channel ID for notifications
- `CHECK_EMAIL_WAIT` - Email check interval in minutes (default: 2)
- `IMAP_SERVER` - IMAP server hostname (default: imap.migadu.com)
- `SMTP_SERVER` - SMTP server hostname (default: smtp.migadu.com)
- `MAX_SESSION_TIME_MINUTES` - Session timeout (default: 2)
- `DISCORD_SENDMSG_CHARACTER_LIMIT` - Message character limit (default: 2000)

### Deployment Process

1. **Push to main branch** - Coolify automatically deploys
2. **Environment variables** - Set via Coolify dashboard
3. **Monitoring** - Check Coolify logs for bot status
4. **Updates** - Simply push new commits to trigger redeployment

## Troubleshooting

### Common Issues

**Bot won't start:**
- Check `.env` file exists and has correct values
- Verify Discord bot token is valid
- Check Python version (3.8+ required)

**Commands not responding:**
- Verify bot has Message Content Intent enabled
- Check bot permissions in Discord server
- Look for error messages in console

**Email monitoring not working:**
- Verify email credentials in `.env`
- Check IMAP server settings
- Test email login manually

**Features not loading:**
- Check syntax errors in feature files
- Verify `setup()` function exists
- Look for import errors in console

### Debug Mode
```bash
# Run with verbose logging
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
exec(open('main.py').read())
"
```

## Resources

- **Discord.py Documentation**: https://discordpy.readthedocs.io/
- **Discord Developer Portal**: https://discord.com/developers/docs/
- **Python Type Hints**: https://docs.python.org/3/library/typing.html
- **Pydantic Settings**: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- **uv Package Manager**: https://docs.astral.sh/uv/