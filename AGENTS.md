# AI Agent Development Guide

This document provides specific guidance for AI agents working on the 508.dev Discord bot project.

📖 **Quick Links:**
- [Main README](README.md) - Project overview and architecture
- [Development Guide](DEVELOPMENT.md) - Setup instructions and coding guidelines
- [Example Cog](bot/cogs/example_cog.py) - Template for new features

## Project Context

This is a **Discord bot** for the 508.dev cooperative.

## Key Architecture Principles

### 1. Feature-Based Modularity
- Each bot feature lives in `bot/features/{feature_name}.py`
- Features are automatically discovered and loaded
- No manual registration required

### 2. Configuration Management
- All settings in `bot/config.py` using Pydantic
- Environment variables loaded automatically
- Type validation and defaults built-in

### 3. Clean Separation
- **main.py**: Minimal entry point
- **bot/bot.py**: Core bot logic and auto-loading
- **bot/features/**: Individual features (commands, events, tasks)
- **bot/utils/**: Shared utilities

## Working with Features

### Creating New Features

1. **Copy the template:**
   ```bash
   cp bot/features/example_feature.py bot/features/{your_feature}.py
   ```

2. **Feature structure:**
   ```python
   from discord.ext import commands
   from bot.config import settings

   class YourFeature(commands.Cog  # Discord.py framework class):
       def __init__(self, bot):
           self.bot = bot

       @commands.command()
       async def your_command(self, ctx):
           await ctx.send("Response")

   async def setup(bot):
       await bot.add_cog  # Discord.py framework method(YourFeature(bot))
   ```

3. **Auto-loading:** Features are loaded automatically on bot restart

### Common Patterns

#### Commands
```python
@commands.command(name="command_name")
async def command_function(self, ctx, arg1: str = None):
    """Command description for help"""
    await ctx.send(f"Hello {ctx.author.mention}")
```

#### Event Listeners
```python
@commands.Cog  # Discord.py framework class.listener()
async def on_message(self, message):
    if message.author.bot:
        return
    # Handle message
```

#### Background Tasks
```python
from discord.ext import tasks

@tasks.loop(minutes=5)
async def background_task(self):
    # Periodic task
    pass

def cog_load  # Discord.py framework method(self):
    self.background_task.start()

def cog_unload  # Discord.py framework method(self):
    self.background_task.cancel()
```

#### Configuration Access
```python
from bot.config import settings

# Access any setting
channel = self.bot.get_channel(settings.channel_id)
```

## File Locations

### Core Files (Rarely Modified)
- `main.py` - Entry point
- `bot/bot.py` - Core bot class
- `bot/config.py` - Settings

### Development Files (Frequently Modified)
- `bot/features/*.py` - Individual features
- `bot/utils/*.py` - Shared utilities
- `pyproject.toml` - Dependencies

### Documentation
- `README.md` - Project overview
- `DEVELOPMENT.md` - Human development guide
- `AGENTS.md` - This file

## Agent-Specific Guidelines

### 1. Feature Isolation
- Always create features in separate files
- Don't modify existing features unless specifically asked
- Use the template as starting point

### 2. Configuration
- Add new settings to `bot/config.py` if needed
- Use environment variables for secrets
- Provide sensible defaults

### 3. Error Handling
```python
@commands.command()
async def safe_command(self, ctx):
    try:
        # Command logic
        await ctx.send("Success")
    except Exception as e:
        await ctx.send(f"Error: {e}")
        print(f"Command error: {e}")
```

### 4. Discord Limits
- Messages max 2000 characters (`settings.discord_sendmsg_character_limit`)
- Use embeds for rich content
- Split long messages into chunks

### 5. Dependencies
- Add to `pyproject.toml` under `dependencies`
- Use `uv add package-name` for installation
- Keep dependencies minimal

## Testing Features

### Manual Testing
```bash
# Run the bot
python main.py

# Test commands in Discord
!your_command
```

### Code Validation
```bash
# Type checking (if available)
mypy bot/

# Code formatting (if available)
black bot/
```

## Common Tasks

### Add Simple Command
1. Copy `example_feature.py`
2. Rename class and file
3. Add `@commands.command()` methods
4. Restart bot

### Add Background Task
1. Import `tasks` from `discord.ext`
2. Use `@tasks.loop()` decorator
3. Start in `cog_load  # Discord.py framework method()`, stop in `cog_unload  # Discord.py framework method()`

### Add Configuration
1. Add field to `Settings` class in `bot/config.py`
2. Use via `settings.your_field`
3. Document required env vars

### Add Event Listener
1. Use `@commands.Cog  # Discord.py framework class.listener()` decorator
2. Method name matches Discord event (`on_message`, `on_member_join`, etc.)

## Debugging

### Common Issues
- **Feature not loading**: Check syntax, `setup()` function exists
- **Commands not working**: Check command name, permissions
- **Config errors**: Verify environment variables, types

### Logging
```python
import logging
logger = logging.getLogger(__name__)

logger.info("Feature loaded")
logger.error(f"Error: {e}")
```

## Best Practices for Agents

1. **Read existing code** before making changes
2. **Follow established patterns** from existing features
3. **Test incrementally** - add one command at a time
4. **Handle errors gracefully** - always use try/catch
5. **Document your work** - add docstrings and comments
6. **Keep features focused** - one feature per file
7. **Use type hints** - helps with code clarity

## Example Feature Ideas

- **Moderation**: Auto-delete spam, warn users
- **Utility**: Weather, reminders, polls
- **508.dev specific**: Member onboarding, project showcases
- **Fun**: Games, jokes, random facts
- **Integrations**: GitHub, calendar, external APIs

Remember: Each feature should be self-contained and focused on a single area of functionality.