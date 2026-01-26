import asyncio
import json
import logging
import aiohttp
import sys
import platform
import time

from controller_commands import COMMANDS_REGISTRY

class ControllerClient:
    """
    A lightweight, standalone Discord WebSocket client for the Controller Bot.
    This bypasses discord.py-self entirely to avoid conflicts with User Account handling.
    """
    def __init__(self, selfbot_client, config_manager):
        self.selfbot = selfbot_client
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.ws = None
        self.session = None
        self.token = None
        self.user_id = None
        self.username = None
        self.sequence = None
        self.session_id = None
        self.heartbeat_interval = 41.250
        self.is_running = False
        self.api_url = "https://discord.com/api/v9"
        self.gateway_url = "wss://gateway.discord.gg/?v=9&encoding=json"
        self._last_heartbeat_sent = 0
        self.latency = float('inf')

    async def start(self, token):
        """Starts the connection to the Gateway."""
        # Strip "Bot " prefix if present, we add it manually where needed
        self.token = token.replace("Bot ", "").strip()
        
        self.logger.info("🎮 Controller Bot: Starting lightweight client...")
        
        async with aiohttp.ClientSession() as session:
            self.session = session
            async with session.ws_connect(self.gateway_url) as ws:
                self.ws = ws
                self.is_running = True
                
                # Start listener loop
                await self.listen()

    async def listen(self):
        """Main WebSocket loop."""
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    op = data.get('op')
                    d = data.get('d')
                    t = data.get('t')
                    s = data.get('s')

                    if s is not None:
                        self.sequence = s

                    if op == 10: # Hello
                        self.heartbeat_interval = d['heartbeat_interval'] / 1000
                        asyncio.create_task(self.heartbeat_loop())
                        await self.identify()
                    
                    elif op == 11: # Heartbeat ACK
                        if self._last_heartbeat_sent:
                            self.latency = (time.time() - self._last_heartbeat_sent)
                    
                    elif op == 0: # Dispatch
                        if t == "READY":
                            self.session_id = d['session_id']
                            self.user_id = d['user']['id']
                            self.username = d['user']['username']
                            self.logger.info(f"🎮 Controller Bot: Connected as {self.username} ({self.user_id})")
                            asyncio.create_task(self.register_commands())
                        
                        elif t == "INTERACTION_CREATE":
                            asyncio.create_task(self.handle_interaction(d))
                            
        except Exception as e:
            self.logger.error(f"❌ Controller Bot Connection Error: {e}")
            self.is_running = False

    async def identify(self):
        """Sends the Identify payload as a proper Bot."""
        payload = {
            "op": 2,
            "d": {
                "token": f"Bot {self.token}",
                "properties": {
                    "$os": sys.platform,
                    "$browser": "discord.py",
                    "$device": "discord.py"
                },
                "compress": False,
                "large_threshold": 250,
                "intents": 1 # GUILDS
            }
        }
        await self.send_json(payload)

    async def heartbeat_loop(self):
        """Sends heartbeats to keep connection alive."""
        self.logger.debug("❤️ Heartbeat loop started")
        while self.is_running and self.ws and not self.ws.closed:
            try:
                self._last_heartbeat_sent = time.time()
                payload = {"op": 1, "d": self.sequence}
                await self.send_json(payload)
                await asyncio.sleep(self.heartbeat_interval)
            except Exception:
                break

    async def send_json(self, payload):
        """Helper to send JSON to WS."""
        if self.ws and not self.ws.closed:
            await self.ws.send_json(payload)

    async def register_commands(self):
        """Registers Slash Commands via raw HTTP from Registry."""
        url = f"{self.api_url}/applications/{self.user_id}/commands"
        headers = {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json"
        }
        
        # Build command list from registry
        commands = []
        subcommand_count = 0
        
        for cmd in COMMANDS_REGISTRY.values():
            cmd_data = None
            if hasattr(cmd, 'get_data'):
                # It's a CommandGroup
                cmd_data = cmd.get_data()
            else:
                # It's a simple command dict
                cmd_data = cmd["data"]
            
            commands.append(cmd_data)
            
            # Count subcommands if present
            options = cmd_data.get('options', [])
            for opt in options:
                if opt.get('type') in (1, 2): # SUB_COMMAND or SUB_COMMAND_GROUP
                     subcommand_count += 1
                     # If nested group (2), count its children too?
                     # Let's count actionable endpoints (leaves).
                     if opt.get('type') == 2:
                         subcommand_count += len(opt.get('options', []))
                         subcommand_count -= 1 # Remove the group itself from count if we only want leaves, or keep text simple.
                         # Actually simpliest is just count total actionable items.
        
        # Recalculate pure actionable count:
        total_actionable = 0
        for cmd in commands:
            opts = cmd.get('options', [])
            has_subs = False
            for opt in opts:
                if opt.get('type') == 1:
                    total_actionable += 1
                    has_subs = True
                elif opt.get('type') == 2:
                    total_actionable += len(opt.get('options', []))
                    has_subs = True
            
            if not has_subs:
                total_actionable += 1

        try:
            async with self.session.put(url, headers=headers, json=commands) as r:
                if r.status in (200, 201):
                    self.logger.info(f"✅ Controller Bot: {len(commands)} Root Commands / {total_actionable} Total Actionable Registered")
                else:
                    text = await r.text()
                    self.logger.error(f"❌ Failed to register commands: {r.status} - {text}")
        except Exception as e:
            self.logger.error(f"❌ Error registering commands: {e}")

    # --- Interaction Response Helpers (Public) ---

    async def send_message(self, channel_id, content=None, embeds=None):
        """Sends a message directly to a channel (without interaction)."""
        url = f"{self.api_url}/channels/{channel_id}/messages"
        
        payload = {}
        if content:
            payload["content"] = str(content)
        if embeds:
            payload["embeds"] = [e.to_dict() if hasattr(e, 'to_dict') else e for e in embeds]
            
        try:
            async with self.session.post(url, json=payload) as r:
                if r.status in (200, 201):
                    return await r.json()
                else:
                    self.logger.error(f"Failed to send message: {r.status} - {await r.text()}")
                    return None
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            return None

    async def send_response(self, interaction, content=None, embeds=None, ephemeral=None):
        """Send an immediate response to an interaction."""
        if ephemeral is None:
            ephemeral = self.config_manager.get("discord.controller_ephemeral", True)
            
        interaction_id = interaction['id']
        interaction_token = interaction['token']
        url = f"{self.api_url}/interactions/{interaction_id}/{interaction_token}/callback"
        
        data_payload = {
            "flags": 64 if ephemeral else 0
        }
        if content:
            data_payload["content"] = str(content)
        
        if embeds:
            # Convert discord.py Embed objects if necessary
            data_payload["embeds"] = [e.to_dict() if hasattr(e, 'to_dict') else e for e in embeds]

        json_payload = {
            "type": 4, # CHANNEL_MESSAGE_WITH_SOURCE
            "data": data_payload
        }
        try:
            await self.session.post(url, json=json_payload)
        except Exception as e:
            self.logger.error(f"Failed to respond to interaction: {e}")
            
    async def defer(self, interaction, ephemeral=None):
        """Defer the response (thinking state)."""
        if ephemeral is None:
            ephemeral = self.config_manager.get("discord.controller_ephemeral", True)
            
        interaction_id = interaction['id']
        interaction_token = interaction['token']
        url = f"{self.api_url}/interactions/{interaction_id}/{interaction_token}/callback"
        json_payload = {"type": 5, "data": {"flags": 64 if ephemeral else 0}}
        try:
            await self.session.post(url, json=json_payload)
        except:
            pass

    async def followup(self, interaction, content=None, embeds=None, ephemeral=None):
        """Send a followup message (after defer)."""
        if ephemeral is None:
            ephemeral = self.config_manager.get("discord.controller_ephemeral", True)
            
        interaction_token = interaction['token']
        # webhooks/{application_id}/{interaction_token}
        url = f"{self.api_url}/webhooks/{self.user_id}/{interaction_token}"
        
        payload = {"flags": 64 if ephemeral else 0}
        if content:
            payload["content"] = str(content)
        if embeds:
            payload["embeds"] = [e.to_dict() if hasattr(e, 'to_dict') else e for e in embeds]

        try:
            await self.session.post(url, json=payload)
        except:
            pass

    async def send_autocomplete_result(self, interaction, choices):
        """Send autocomplete choices."""
        interaction_id = interaction['id']
        interaction_token = interaction['token']
        url = f"{self.api_url}/interactions/{interaction_id}/{interaction_token}/callback"
        
        json_payload = {
            "type": 8, # APPLICATION_COMMAND_AUTOCOMPLETE_RESULT
            "data": {
                "choices": choices # list of {name, value}
            }
        }
        try:
            async with self.session.post(url, json=json_payload) as r:
                if r.status not in (200, 204):
                    text = await r.text()
                    self.logger.error(f"Failed to send autocomplete: {r.status} - {text}")
        except Exception as e:
            self.logger.error(f"Failed to send autocomplete: {e}")

    async def handle_interaction(self, data):
        """Handles incoming slash commands using Registry."""
        try:
            command_name = data['data']['name']
            
            # --- LOGGING: Log command usage to UI (exclude /embed) ---
            if command_name != "embed" and data['type'] != 4: # Not Autocomplete
                 try:
                     # Construct full command name with subcommands
                     full_command = f"/{command_name}"
                     current_options = data['data'].get('options', [])
                     
                     # Check for Subcommand (1) or Subcommand Group (2)
                     if current_options and current_options[0]['type'] in (1, 2):
                         # It's a subcommand or group
                         sub_name = current_options[0]['name']
                         full_command += f" {sub_name}"
                         
                         # Check for nested subcommand (if it was a group)
                         if current_options[0]['type'] == 2 and current_options[0].get('options'):
                             nested_opts = current_options[0]['options']
                             if nested_opts and nested_opts[0]['type'] == 1:
                                 full_command += f" {nested_opts[0]['name']}"

                     if hasattr(self.selfbot, 'ui_callback') and self.selfbot.ui_callback:
                        # Try to get better names using Selfbot cache
                        channel_id_raw = data.get('channel_id')
                        guild_id_raw = data.get('guild_id')
                        
                        channel_name = f"Channel {channel_id_raw}" if channel_id_raw else "Unknown Channel"
                        guild_name_str = "DM" # Default if no guild_id

                        if channel_id_raw:
                            try:
                                ch_obj = self.selfbot.get_channel(int(channel_id_raw))
                                if ch_obj:
                                    if hasattr(ch_obj, 'name'):
                                        channel_name = f"#{ch_obj.name}"
                                    elif hasattr(ch_obj, 'recipient'): # DM
                                        channel_name = f"@{ch_obj.recipient.name}"
                                    else:
                                        channel_name = "Direct Message"
                            except:
                                pass

                        if guild_id_raw:
                            try:
                                g_obj = self.selfbot.get_guild(int(guild_id_raw))
                                if g_obj:
                                    guild_name_str = g_obj.name
                                else:
                                    guild_name_str = f"Guild {guild_id_raw}"
                            except:
                                guild_name_str = f"Guild {guild_id_raw}"
                        
                        self.selfbot.ui_callback('command_used', {
                            'command': full_command,
                            'channel': channel_name,
                            'guild': guild_name_str
                        })
                 except Exception as log_err:
                     self.logger.warning(f"Failed to log command usage: {log_err}")
            # ---------------------------------------------------------

            # Look up command in registry
            cmd_def = COMMANDS_REGISTRY.get(command_name)
            
            if cmd_def:
                # Check if it's a CommandGroup
                if hasattr(cmd_def, 'subcommands'):
                    options = data['data'].get('options', [])
                    if options and options[0]['type'] == 1: # SUB_COMMAND
                        sub_name = options[0]['name']
                        sub_cmd = cmd_def.subcommands.get(sub_name)
                        
                        if sub_cmd:
                            # Check interaction type
                            if data['type'] == 4: # Autocomplete
                                if sub_cmd.get("autocomplete"):
                                    await sub_cmd["autocomplete"](self, data)
                            else:
                                await sub_cmd["callback"](self, data)
                        else:
                            self.logger.warning(f"Unknown subcommand: {sub_name}")
                
                elif cmd_def.get("callback"):
                    # Simple command
                    if data['type'] == 4: # Autocomplete
                        if cmd_def.get("autocomplete"):
                            await cmd_def["autocomplete"](self, data)
                    else:
                        await cmd_def["callback"](self, data)
            else:
                self.logger.warning(f"Unknown command received: {command_name}")
                    
        except Exception as e:
            self.logger.error(f"Error handling interaction: {e}")
