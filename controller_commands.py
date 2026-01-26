import logging
import pkgutil
import importlib
import sys
import os

# Registry to store command definitions and callbacks
COMMANDS_REGISTRY = {}

class Option:
    SUB_COMMAND = 1
    SUB_COMMAND_GROUP = 2
    STRING = 3
    INTEGER = 4
    BOOLEAN = 5
    USER = 6
    CHANNEL = 7
    ROLE = 8
    MENTIONABLE = 9
    NUMBER = 10
    ATTACHMENT = 11

    def __new__(cls, name, description, type=STRING, required=True, autocomplete=False):
        """Helper to create an option dictionary."""
        return {
            "name": name,
            "description": description,
            "type": type,
            "required": required,
            "autocomplete": autocomplete
        }

def get_arg(interaction, name, default=None):
    """
    Helper to retrieve an argument value from an interaction.
    Handles nested Subcommands automatically!
    """
    data = interaction.get('data', {})
    options = data.get('options', [])

    # Recursive search for the argument value
    def search_options(opts):
        for o in opts:
            if o['type'] in (Option.SUB_COMMAND, Option.SUB_COMMAND_GROUP):
                # Dive deeper
                res = search_options(o.get('options', []))
                if res is not None: return res
            elif o['name'] == name:
                return o['value']
        return None
    
    val = search_options(options)
    return val if val is not None else default

class CommandGroup:
    """Helper class to create Subcommand Groups (e.g. /troll spam)."""
    def __init__(self, name, description):
        self.name = name
        self.description = description
        self.subcommands = {} # name -> {callback, data}
        # Register self immediately
        COMMANDS_REGISTRY[name] = self

    def command(self, name, description, options=None, autocomplete=None):
        """Decorator to add a subcommand to this group."""
        def decorator(func):
            self.subcommands[name] = {
                "callback": func,
                "autocomplete": autocomplete,
                "data": {
                    "name": name,
                    "description": description,
                    "type": Option.SUB_COMMAND,
                    "options": options or []
                }
            }
            return func
        return decorator
    
    def get_data(self):
        """Returns the full JSON data structure for Discord."""
        return {
            "name": self.name,
            "description": self.description,
            "type": 1, # CHAT_INPUT
            "integration_types": [0, 1],
            "contexts": [0, 1, 2],
            "options": [sub["data"] for sub in self.subcommands.values()]
        }

def controller_command(name, description, options=None, autocomplete=None):
    """Decorator to register a top-level Slash Command."""
    def decorator(func):
        COMMANDS_REGISTRY[name] = {
            "data": {
                "name": name,
                "description": description,
                "type": 1,
                "integration_types": [0, 1],
                "contexts": [0, 1, 2],
                "options": options or []
            },
            "callback": func,
            "autocomplete": autocomplete
        }
        return func
    return decorator

async def send_smart_embed(client, interaction, embed, delete_after=None):
    """
    Sends an embed by having the Selfbot invoke the Controller Bot's /embed command,
    then forwarding the resulting message to the target channel.
    
    Flow:
    1. Selfbot opens DM with Controller Bot
    2. Selfbot invokes /embed command with embed data
    3. Wait for Controller's response message with the embed
    4. Forward that message to the target channel (if forwarding is ON)
    5. Or just confirm success (if forwarding is OFF, embed stays in DM)
    """
    import discord
    import logging
    import asyncio
    logger = logging.getLogger(__name__)
    
    try:
        # === OPTIMIZATION: Check Forwarding Logic First ===
        # If Forwarding is Disabled, we don't need the Controller Bot loop at all.
        # We can just send the embed immediately as an ephemeral response (Private Preview).
        
        is_forwarding = client.config_manager.get("discord.controller_forwarding", False)
        if not is_forwarding:
            await client.followup(interaction, embeds=[embed], ephemeral=True)
            return

        # === Step 1: Get DM channel with Controller Bot ===
        controller_user = client.selfbot.get_user(int(client.user_id))
        if not controller_user:
            controller_user = await client.selfbot.fetch_user(int(client.user_id))
        
        if not controller_user:
            logger.error("Could not find Controller Bot user")
            await client.followup(interaction, "❌ Could not find Controller Bot user.")
            return
            
        if not controller_user.dm_channel:
            await controller_user.create_dm()
        
        dm_channel = controller_user.dm_channel
        
        # === Step 2: Find and invoke the /embed command ===
        # application_commands() returns a list (no params), filter manually
        all_commands = await dm_channel.application_commands()
        embed_cmd = None
        for cmd in all_commands:
            if cmd.name == "embed" and cmd.application_id == int(client.user_id):
                embed_cmd = cmd
                break
        
        if not embed_cmd:
            logger.error("Could not find /embed command from Controller Bot")
            await client.followup(interaction, "❌ Could not find `/embed` command on Controller Bot.")
            return
        
        # Extract embed data for command options
        # Title = embed title (command name)
        embed_title = embed.title
        
        # Content = description + fields formatted as text
        content_lines = []
        
        if embed.description:
            content_lines.append(embed.description)
        
        # Format fields as text
        if embed.fields:
            content_lines.append("")  # Blank line
            for field in embed.fields:
                content_lines.append(f"**{field.name}**: {field.value}")
        
        embed_content = "\n".join(content_lines)
        
        # Image handling
        embed_image_url = None
        embed_is_thumb = True
        
        if embed.image and embed.image.url:
            embed_image_url = embed.image.url
        elif embed.thumbnail and embed.thumbnail.url:
            embed_image_url = embed.thumbnail.url
            embed_is_thumb = True
        
        # Build kwargs
        cmd_kwargs = {}
        if embed_content:
            cmd_kwargs["content"] = embed_content
        if embed_title:
            cmd_kwargs["title"] = embed_title
        if embed_image_url:
            cmd_kwargs["image_url"] = embed_image_url
            cmd_kwargs["thumb"] = embed_is_thumb
        if delete_after:
            cmd_kwargs["delete_after"] = int(delete_after)
            
        # Pass author name if present in the original embed
        if embed.author and embed.author.name:
            cmd_kwargs["author_name"] = embed.author.name
        
        # === Step 3: Handle Based on Forwarding Config ===
        is_forwarding = client.config_manager.get("discord.controller_forwarding", False)

        # If Forwarding is OFF: The embed will be Ephemeral (Private).
        # We CANNOT wait for a message event because ephemeral messages don't trigger on_message.
        # So we just invoke and assume success.
        
        if not is_forwarding:
            # Invoke command (Ephemeral)
            embed_cmd.target_channel = dm_channel
            await embed_cmd(**cmd_kwargs)
            logger.info(f"✅ Invoked /embed command (Ephemeral - No Forwarding)")
            await client.followup(interaction, "✅ Embed sent (Private Preview).")
            return

        # If Forwarding is ON: The embed is Public in DM.
        # We start listening for the message so we can forward it.

        def check_initial(m):
            is_author = m.author.id == int(client.user_id)
            is_channel = m.channel.id == dm_channel.id
            return (is_author and is_channel)

        # Start listening for the INITIAL message (possibly just "Thinking...")
        response_task = asyncio.create_task(client.selfbot.wait_for('message', check=check_initial, timeout=10.0))

        # Invoke the slash command
        embed_cmd.target_channel = dm_channel
        await embed_cmd(**cmd_kwargs)
        
        logger.info(f"✅ Invoked /embed command in DM with Controller Bot")
        
        # Now wait for the task to complete
        try:
            response_msg = await response_task
            
            # === Handle Deferred Responses (Thinking...) ===
            # If we caught the "Thinking..." message, it won't have embeds yet.
            # We need to wait for the bot to EDIT this message with the actual content.
            if not response_msg.embeds:                
                def check_edit(before, after):
                    return (after.id == response_msg.id and len(after.embeds) > 0)
                
                try:
                    # Wait for the edit that adds embeds
                    _, response_msg = await client.selfbot.wait_for('message_edit', check=check_edit, timeout=10.0)
                except asyncio.TimeoutError:
                    logger.warning("Timed out waiting for message edit (Embed population)")
                    await client.followup(interaction, "⚠️ Controller Bot sent a message but never added the embed.")
                    return
        except asyncio.TimeoutError:
            logger.warning("Timed out waiting for embed response from Controller")
            await client.followup(interaction, "⚠️ Timed out waiting for Controller Bot response.")
            return
        
        # === Step 4: Handle forwarding ===
        # Forward the message to the target channel
        channel_id_raw = interaction.get('channel_id')
        current_channel_id = int(channel_id_raw) if channel_id_raw else 0
        
        target_channel = client.selfbot.get_channel(current_channel_id)
        if not target_channel:
            try: 
                target_channel = await client.selfbot.fetch_channel(current_channel_id)
            except: 
                pass
        
        if target_channel:
            # Forward the message!
            await response_msg.forward(target_channel)
            
            # Mark as read in DM since we forwarded it
            try:
                await response_msg.ack()
            except Exception as e:
                logger.warning(f"Failed to ack message: {e}")

            logger.info(f"✅ Forwarded embed to channel {current_channel_id}")
            await client.followup(interaction, "✅ Embed forwarded successfully!")
        else:
            await client.followup(interaction, "❌ Could not access target channel for forwarding.")
            
    except Exception as e:
        logger.error(f"Error in send_smart_embed: {e}")
        await client.followup(interaction, f"❌ Failed to send embed: {e}")

def load_cogs():
    """
    Dynamically loads all modules in the 'controller_cogs' folder.
    This mimics the Discord.py Cogs system.
    """
    cogs_dir = "controller_cogs"
    
    if not os.path.exists(cogs_dir):
        logging.getLogger(__name__).warning("⚠️ 'controller_cogs' directory not found. Skipping auto-load.")
        return

    # Add current directory to path just in case
    if os.getcwd() not in sys.path:
        sys.path.append(os.getcwd())

    loaded_count = 0
    try:
        # Iterate over files in the directory
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = f"{cogs_dir}.{filename[:-3]}"
                try:
                    importlib.import_module(module_name)
                    logging.getLogger(__name__).info(f"🧩 Loaded Cog: {filename}")
                    loaded_count += 1
                except Exception as e:
                    logging.getLogger(__name__).error(f"❌ Failed to load {filename}: {e}")
                    
        logging.getLogger(__name__).info(f"✅ Loaded {loaded_count} Extension Modules")

    except Exception as e:
        logging.getLogger(__name__).error(f"❌ Error loading cogs: {e}")

def get_embed_style(client):
    """
    Helper to retrieve centralized embed styling from config.
    Returns a dict with resolved values:
    - author_text
    - author_icon_url
    - thumbnail_url
    - footer_text
    - footer_icon_url
    - color (int)
    """
    embed_config = client.config_manager.get("embed", {})
    
    style = {
        "author_text": embed_config.get("author_text", "Orbyte"),
        "author_icon_url": embed_config.get("author_icon_url", ""),
        "thumbnail_url": embed_config.get("thumbnail_url", ""),
        "footer_text": embed_config.get("footer_text", "# Orbyte Selfbot"),
        "footer_icon_url": embed_config.get("footer_icon_url", ""),
        "color": 0x2b2d31 # Default
    }
    
    color_hex = embed_config.get("color", "2b2d31")
    try:
        style["color"] = int(color_hex, 16)
    except:
        pass
        
    return style
