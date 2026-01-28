import discord
from discord.ext import commands
from controller_worker import ControllerClient
from controller_commands import load_cogs
import aiohttp
import asyncio
import logging
import threading
import sqlite3
import os
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional, Dict
import io
import contextlib
import traceback
import sys
import re
import time
import json

class BotWorker:
    """
    Main class for managing the Discord selfbot with a decorator-based command system.
    """
    def __init__(self, config_manager, ui_callback: Optional[Callable] = None):
        self.config_manager = config_manager
        self.ui_callback = ui_callback
        self.client: Optional[commands.Bot] = None
        self.controller_client: Optional[ControllerClient] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self._login_complete = threading.Event()
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.nitro_regex = re.compile(r"(?:discord\.gift/|discord(?:app)?\.com/gifts/)([a-zA-Z0-9]{16,24})")

        # Logging configuration
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        logging.getLogger('discord').setLevel(logging.WARNING)

        # Initialize Database
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(self.base_dir, "activity.db")
        self._init_db()
        
        # Track resources created by scripts
        self.script_commands = {} # filename -> [command_names]
        self.script_listeners = {} # filename -> [(event_name, func)]

    def _init_db(self):
        """Initialize sqlite database for activity logs."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            c = conn.cursor()
            # Activity Log
            c.execute('''CREATE TABLE IF NOT EXISTS activity_log
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          type TEXT,
                          timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            
            # User History (Username tracking)
            c.execute('''CREATE TABLE IF NOT EXISTS user_history
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          user_id TEXT,
                          username TEXT,
                          timestamp INTEGER)''')

            # Last Seen
            c.execute('''CREATE TABLE IF NOT EXISTS last_seen
                         (user_id TEXT PRIMARY KEY,
                          timestamp INTEGER)''')

            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Failed to init DB: {e}")

    def log_activity(self, activity_type: str):
        """Log an activity to the database."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            c = conn.cursor()
            c.execute("INSERT INTO activity_log (type) VALUES (?)", (activity_type,))
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Failed to log activity {activity_type}: {e}")

    def _track_username(self, user_id, username):
        """Internal helper to save username history."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            c = conn.cursor()
            # Check if the latest entry is different to avoid dupes
            c.execute("SELECT username FROM user_history WHERE user_id=? ORDER BY timestamp DESC LIMIT 1", (str(user_id),))
            last = c.fetchone()
            if not last or last[0] != username:
                c.execute("INSERT INTO user_history (user_id, username, timestamp) VALUES (?, ?, ?)", 
                          (str(user_id), username, int(datetime.now().timestamp())))
                conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Failed to track username: {e}")

    def _track_last_seen(self, user_id):
        """Internal helper to update last seen."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO last_seen (user_id, timestamp) VALUES (?, ?)", 
                      (str(user_id), int(datetime.now().timestamp())))
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Failed to track last seen: {e}")

    # === Public Data Accessors for Commands ===

    def get_user_history(self, user_id):
        """Returns list of {username, timestamp} for a user."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            c = conn.cursor()
            c.execute("SELECT username, timestamp FROM user_history WHERE user_id=? ORDER BY timestamp DESC LIMIT 10", (str(user_id),))
            rows = c.fetchall()
            conn.close()
            return [{'username': r[0], 'timestamp': r[1]} for r in rows]
        except Exception:
            return []

    def get_last_seen(self, user_id):
        """Returns timestamp (int) or None."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            c = conn.cursor()
            c.execute("SELECT timestamp FROM last_seen WHERE user_id=?", (str(user_id),))
            row = c.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception:
            return None

    def get_header(self):
        """
        Returns authentication headers for Discord API requests.
        """
        token = self.config_manager.get_token()
        return {
            "Authorization": token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) discord/1.0.9001 Chrome/83.0.4103.122 Electron/9.3.5 Safari/537.36"
        }

    async def _start_bot_internal(self, token: str):
        """
        Starts the selfbot.
        """
        # Apply Platform Spoofing
        try:
            from platform_spoofer import PlatformSpoofer
            platform = self.config_manager.get("discord.platform", "desktop")
            PlatformSpoofer.patch(platform)
        except Exception as e:
            self.logger.error(f"Failed to apply platform spoofing: {e}")

        # Initialize Client
        self.client = commands.Bot(command_prefix=self.config_manager.get("discord.command_prefix"), self_bot=True, help_command=None)
        
        # Attach extras
        if self.ui_callback:
            setattr(self.client, 'ui_callback', self.ui_callback)
        self.client.log_activity = self.log_activity
        
        # Attach Data Accessors to Client so commands can use them
        self.client.get_user_history = self.get_user_history
        self.client.get_last_seen = self.get_last_seen

        # Register Events and Commands
        self._register_events()

        # Setup Controller Bot if token exists
        controller_token = self.config_manager.get("discord.controller_token")
        if controller_token:
            self.logger.info("🎮 Initializing Controller Bot (Lightweight Client)...")
            load_cogs() # Load all commands from the folder
            
            self.controller_client = ControllerClient(self.client, config_manager=self.config_manager)
        else:
            self.logger.info("ℹ️ No Controller Token found. Running in Selfbot-only mode.")

        @self.client.event
        async def on_ready():
            self.logger.info(f"✅ Logged in as {self.client.user}")
            # EVENT: Logged in
            if self.ui_callback:
                self.ui_callback('ready', {
                    'username': self.client.user.name,
                    'discriminator': self.client.user.discriminator,
                    'avatar_url': str(self.client.user.avatar.url if self.client.user.avatar else ""),
                    'id': str(self.client.user.id)
                })
            
            self.is_running = True
            self._login_complete.set()
            
            # EVENT: Fetching data
            if self.ui_callback:
                self.ui_callback('startup_progress', {'message': "Fetching profile data..."})
            
            asyncio.create_task(self._update_user_data())
            # Updates user info every 5 minutes
            while self.is_running:
                await asyncio.sleep(300)
                await self._update_user_data()

        # Connect and Login
        await self._connect_and_login(token, controller_token)

    def _register_events(self):
        """
        Registers all event listeners and commands for the Selfbot.
        Keeps the main startup logic clean.
        """
        bot = self.client

        @bot.event
        async def on_reaction_add(reaction, user):
            # Log Activity: Reaction Added
            if user == bot.user:
                 self.log_activity('reaction_added')

        @bot.event
        async def on_message_delete(message):
            # Ghost Ping Detection
            if message.guild and message.author != message.guild.me:
                is_mentioned = message.guild.me in message.mentions
                is_role_mentioned = any(role in message.guild.me.roles for role in message.role_mentions)
                
                if is_mentioned or is_role_mentioned:
                    time_diff = (datetime.now(timezone.utc) - message.created_at).total_seconds()
                    
                    if time_diff < 300:
                        await self._send_webhook("ghostpings", {
                            "title": "👻 Ghost Ping Detected",
                            "description": f"**Server:** {message.guild.name}\n**Channel:** {message.channel.mention}\n**Author:** {message.author.mention} (`{message.author.id}`)\n**Content:** {message.content}",
                            "color": 0x99AAB5,
                        })

        @bot.event
        async def on_message(message):
            if self.config_manager.get("nitro_sniper", False):
                if message.author != bot.user:
                    search = self.nitro_regex.search(message.content)
                    if search:
                        code = search.group(1)
                        start_time = time.perf_counter()
                        
                        headers = self.get_header()
                        url = f"https://discord.com/api/v9/entitlements/gift-codes/{code}/redeem"
                        
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.post(url, headers=headers, json={'channel_id': message.channel.id}) as resp:
                                    latency = (time.perf_counter() - start_time) * 1000
                                    
                                    if resp.status == 200:
                                        self.log_activity(f"Sniper: Claimed {code} in {latency:.2f}ms")
                                        self.logger.info(f"🚀 Nitro Sniper: Claimed code {code} in {latency:.2f}ms")
                                        if self.ui_callback:
                                            self.ui_callback('sniper_log', {'code': code, 'status': 'claimed', 'time': f"{latency:.2f}ms"})
                                        
                                        await self._send_webhook("nitro_snipes", {
                                            "title": "🚀 Nitro Sniper: Claimed!",
                                            "description": f"**Code:** `{code}`\n**Time:** `{latency:.2f}ms`\n**Server:** {message.guild.name if message.guild else 'DM'}",
                                            "color": 0x57F287,
                                        })

                                    elif resp.status == 400: # Unknown Gift
                                        self.log_activity(f"Sniper: Invalid {code}")
                                        self.logger.info(f"💥 Nitro Sniper: Invalid code {code} ({latency:.2f}ms)")
                                        if self.ui_callback:
                                            self.ui_callback('sniper_log', {'code': code, 'status': 'invalid', 'time': f"{latency:.2f}ms"})
                                        
                                        # Webhook: Nitro Invalid
                                        await self._send_webhook("nitro_snipes", {
                                            "title": "💥 Nitro Sniper: Invalid Code",
                                            "description": f"**Code:** `{code}`\n**Time:** `{latency:.2f}ms`\n**Status:** Invalid/Unknown Gift",
                                            "color": 0xED4245, # Red
                                        })

                                    elif resp.status == 429: # Ratelimit
                                        self.log_activity(f"Sniper: RateLimited {code}")
                                        self.logger.warning(f"⏳ Nitro Sniper: RateLimited on {code}")
                                        
                                        await self._send_webhook("nitro_snipes", {
                                            "title": "⏳ Nitro Sniper: Rate Limited",
                                            "description": f"**Code:** `{code}`",
                                            "color": 0xFEE75C, # Yellow
                                        })

                                    else:
                                        self.log_activity(f"Sniper: Failed {code} ({resp.status})")
                                        self.logger.info(f"❓ Nitro Sniper: Failed {code} - Status {resp.status}")
                                        
                                        await self._send_webhook("nitro_snipes", {
                                            "title": "❓ Nitro Sniper: Failed",
                                            "description": f"**Code:** `{code}`\n**Status Code:** `{resp.status}`",
                                            "color": 0xED4245, # Red
                                        })

                        except Exception as e:
                             self.logger.error(f"Sniper Error: {e}")

            # Log Activity: Message Sent
            if bot.user == message.author:
                self.log_activity('message_sent')

            # Log Activity: Ping Received
            if bot.user in message.mentions:
                self.log_activity('ping_received')

            # Handle Mention Everyone/Here
            if message.mention_everyone and message.author != message.guild.me:
                if self.ui_callback:
                    self.ui_callback('ping_received', {
                        'user': str(message.author.name),
                        'server_name': str(message.guild.name),
                        'content': message.content,
                        'guild_id': str(message.guild.id),
                        'channel_id': str(message.channel.id),
                        'message_id': str(message.id)
                    })
                
                # Webhook: Ping Received (Everyone/Here)
                await self._send_webhook("pings", {
                    "title": "🔔 Ping Received (Everyone/Here)",
                    "description": f"**Server:** {message.guild.name}\n**Channel:** {message.channel.mention}\n**Author:** {message.author.mention} (`{message.author.id}`)\n**Content:** {message.content}\n\n[Jump to Message]({message.jump_url})",
                    "color": 0x5865F2,
                })

            # Handle Direct Mentions
            if message.guild and message.guild.me in message.mentions and message.author != message.guild.me:
                if self.ui_callback:
                    # Format content to be readable (replace IDs with names)
                    message_content = message.content.replace(
                        f"<@{message.guild.me.id}>", f"@{message.guild.me.name}"
                    ).strip()
                    for user in message.mentions:
                        if user != message.guild.me:
                            message_content = message_content.replace(
                                f"<@{user.id}>", f"@{user.name}"
                            )
                    
                    self.ui_callback('ping_received', {
                        'user': str(message.author.name),
                        'server_name': str(message.guild.name),
                        'content': message_content,
                        'guild_id': str(message.guild.id),
                        'channel_id': str(message.channel.id),
                        'message_id': str(message.id)
                    })

                # Webhook: Ping Received
                await self._send_webhook("pings", {
                    "title": "🔔 Ping Received",
                    "description": f"**Server:** {message.guild.name}\n**Channel:** {message.channel.mention}\n**Author:** {message.author.mention} (`{message.author.id}`)\n**Content:** {message.content}\n\n[Jump to Message]({message.jump_url})",
                    "color": 0x5865F2,
                })

            # Handle Role Mentions
            if message.guild and message.author != message.guild.me:
                mentioned_roles = [role for role in message.role_mentions if role in message.guild.me.roles]
                if mentioned_roles:
                    role_names = ", ".join([role.name for role in mentioned_roles])
                    if self.ui_callback:
                        message_content = message.content
                        for role in mentioned_roles:
                             message_content = message_content.replace(f"<@&{role.id}>", f"@{role.name}").strip()
                        
                        self.ui_callback('ping_received', {
                            'user': str(message.author.name),
                            'server_name': str(message.guild.name),
                            'content': message_content,
                            'guild_id': str(message.guild.id),
                            'channel_id': str(message.channel.id),
                            'message_id': str(message.id)
                        })

                    # Webhook: Role Ping Received
                    await self._send_webhook("pings", {
                        "title": f"🔔 Role Ping Received ({role_names})",
                        "description": f"**Server:** {message.guild.name}\n**Channel:** {message.channel.mention}\n**Author:** {message.author.mention} (`{message.author.id}`)\n**Content:** {message.content}\n\n[Jump to Message]({message.jump_url})",
                        "color": 0x5865F2,
                    })
            
            # Process Commands
            await bot.process_commands(message)

        @bot.event
        async def on_guild_join(guild):
            if self.ui_callback:
                self.ui_callback('server_joined', {
                    'server_name': str(guild.name),
                    'guild_id': str(guild.id)
                })
            self.log_activity('server_join')
            
        @bot.event
        async def on_guild_remove(guild):
            if self.ui_callback:
                self.ui_callback('server_left', {
                    'server_name': str(guild.name)
                })

        @bot.event
        async def on_relationship_remove(relationship: discord.Relationship):
            if self.ui_callback:
                self.ui_callback('friend_removed', {'user': str(relationship.user.name)})
            
            # Webhook: Unfriended
            await self._send_webhook("unfriended", {
                "title": "💔 Friend Removed",
                "description": f"**User:** {relationship.user.name} (`{relationship.user.id}`)",
                "color": 0xED4245,
            })
        
        @bot.event
        async def on_relationship_add(relationship: discord.Relationship):
            if self.ui_callback:
                user_str = str(relationship.user.name)
                if relationship.type == discord.RelationshipType.friend:
                    self.ui_callback('friend_added', {'user': user_str})
                elif relationship.type == discord.RelationshipType.incoming_request:
                    self.ui_callback('friend_request', {'user': user_str})
                elif relationship.type == discord.RelationshipType.outgoing_request:
                    self.ui_callback('friend_request_sent', {'user': user_str})
                
        @bot.event
        async def on_member_update(before, after):
            # Pass to base tracking
            pass # We'll handle this in user_update for universal tracking
            
            if before.id == bot.user.id:
                # Tracking self roles for UI
                if self.ui_callback:
                    before_roles = set(before.roles)
                    after_roles = set(after.roles)
                    added_roles = after_roles - before_roles
                    removed_roles = before_roles - after_roles
                    
                    for role in added_roles:
                        self.ui_callback('role_added', {
                            'user': str(after),
                            'role_name': str(role),
                            'server_name': str(after.guild.name)
                        })
                    for role in removed_roles:
                        self.ui_callback('role_removed', {
                            'user': str(after),
                            'role_name': str(role),
                            'server_name': str(after.guild.name)
                        })
                
                if added_roles:
                     roles_str = ", ".join([role.name for role in added_roles])
                     await self._send_webhook("new_roles", {
                        "title": "🛡️ Role Added",
                        "description": f"**Server:** {after.guild.name}\n**Role(s):** {roles_str}",
                        "color": 0xF1C40F,
                    })
                
                if removed_roles:
                     roles_str = ", ".join([role.name for role in removed_roles])
                     await self._send_webhook("new_roles", {
                        "title": "🛡️ Role Removed",
                        "description": f"**Server:** {after.guild.name}\n**Role(s):** {roles_str}",
                        "color": 0x95A5A6,
                    })
        
        @bot.event
        async def on_user_update(before, after):
            """Track username changes and last seen."""
            if before.name != after.name or before.discriminator != after.discriminator:
                self._track_username(after.id, f"{after.name}#{after.discriminator}")
        
        @bot.event
        async def on_presence_update(before, after):
            """Track last seen when a user goes offline or changes status."""
            if after.status != discord.Status.offline:
                 self._track_last_seen(after.id)

    async def _connect_and_login(self, token, controller_token):
        """Helper to run the login logic."""
        try:
            self.logger.info("🔑 Attempting to log in...")
            if self.ui_callback:
                self.ui_callback('startup_progress', {'message': "Connecting to Discord Gateway..."})
            
            # Start Selfbot
            loop = asyncio.get_running_loop()
            
            async def run_selfbot():
                try:
                    await self.client.start(token)
                except discord.LoginFailure:
                    self.logger.error("❌ Selfbot Login Failed: Invalid User Token.")
                    self._login_complete.set()
                except Exception as e:
                    self.logger.error(f"❌ Selfbot Error: {e}")
                    self._login_complete.set()

            async def run_controller():
                try:
                    self.logger.info("🎮 Starting Controller Bot...")
                    clean_token = controller_token.strip()
                    # The new client handles the connection logic fully (including Bot prefix)
                    await self.controller_client.start(clean_token)
                except Exception as e:
                    self.logger.error(f"❌ Controller Bot Error: {e}")

            tasks = [loop.create_task(run_selfbot())]
            
            if self.controller_client and controller_token:
                tasks.append(loop.create_task(run_controller()))
            
            # Wait for first exception or completion
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
            
            # If any task failed, handle it
            for task in done:
                if task.exception():
                    # Log exception if needed, though run_ wrapper handles it
                    pass

        except Exception as e:
            self.logger.exception(f"❌ Unexpected error in main loop: {e}")
            self._login_complete.set()

            tasks = [loop.create_task(run_selfbot())]
            
            if self.controller_client and controller_token:
                tasks.append(loop.create_task(run_controller()))
            
            await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
            
            # Keep running until one fails or stops
            await asyncio.gather(*tasks)

        except Exception as e:
            self.logger.exception(f"❌ Unexpected error in main loop: {e}")
            self._login_complete.set()

    def validate_and_start(self, token: str, timeout: int = 120):
        """
        Starts the bot in a thread and waits for user_data to be sent (or timeout).
        Returns {'success': True} only if user_data was successfully sent.
        """
        if self.is_running:
            return {'success': False, 'error': 'Bot is already running.'}

        self._login_complete.clear()
        result = {'success': False, 'error': 'Login timed out.'}

        def runner():
            try:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                self.loop.run_until_complete(self._start_bot_internal(token))
            except Exception as e:
                self.logger.exception(f"Exception in bot thread: {e}")
                self._login_complete.set()

        self.thread = threading.Thread(target=runner, daemon=True)
        self.thread.start()

        happened = self._login_complete.wait(timeout=timeout)

        if not happened:
            if self.loop and not self.loop.is_closed():
                try:
                    asyncio.run_coroutine_threadsafe(self.client.close(), self.loop)
                except Exception:
                    pass
            return result

        if self.is_running:
            try:
                self.config_manager.update_token(token)
            except Exception:
                pass
            return {'success': True}
        else:
            return {'success': False, 'error': 'Login failed.'}

    async def _update_user_data(self):
        """
        Fetches and sends user info (badges, nitro, etc.) to the frontend.
        """
        if not self.client or not self.client.user:
            return

        user = self.client.user
        nitro_type = "None"
        display = "No Subscription"
        badges = []

        # Fetch Nitro subscription and status
        try:
            if self.ui_callback:
                 self.ui_callback('startup_progress', {'message': "Checking Nitro subscription..."})
            sub_nitro = await self.client.subscriptions()
            if sub_nitro:
                sub = sub_nitro[0]
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://discord.com/api/v9/users/@me", headers=self.get_header()) as r:
                        if r.status == 200:
                            data = await r.json()
                            premium_type = data.get("premium_type", 0)
                            if premium_type == 1:
                                nitro_type = "Nitro Classic"
                            elif premium_type == 2:
                                nitro_type = "Nitro Boost"
                            elif premium_type == 3:
                                nitro_type = "Nitro Basic"
                            else:
                                nitro_type = "No Active Subscription"
                        else:
                            nitro_type = "Unknown"
                status = sub.status.name.capitalize()
                if status.lower() in ("canceled", "ended"):
                    now = datetime.now(timezone.utc)
                    days_left = (sub.current_period_end - now).days if sub.current_period_end else None
                    expire_info = f"{days_left} days left" if days_left and days_left > 0 else "expired"
                    if sub.grace_period and sub.grace_period_expires_at:
                        grace_days = (sub.grace_period_expires_at - now).days
                        expire_info += f", grace period: {grace_days} days left" if grace_days > 0 else ", grace period expired"
                else:
                    if sub.current_period_end:
                        now = datetime.now(timezone.utc)
                        days_left = (sub.current_period_end - now).days
                        expire_info = f"{days_left} days left" if days_left > 0 else "expired"
                    else:
                        expire_info = "no end date"
                display = f"{nitro_type} ({status}, {expire_info})"
        except Exception as e:
            self.logger.warning(f"Error fetching Nitro: {e}")

        # Fetch badges from modified clients
        client_badges = []
        try:
            if self.ui_callback:
                 self.ui_callback('startup_progress', {'message': "Loading client badges..."})
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.domi-btnr.dev/clientmodbadges/users/{user.id}/") as r:
                    if r.status == 200:
                        content_type = r.headers.get('Content-Type', '')
                        if 'application/json' in content_type:
                            badges_data = await r.json()

                            clients = ['Aliucord', 'BetterDiscord', 'BadgeVault', 'Enmity', 'Replugged', 'Vencord']
                            for client in clients:
                                for badge in badges_data.get(client, []):
                                    badge_name = ""
                                    badge_url = ""

                                    if isinstance(badge, dict):
                                        badge_name = badge.get('name', '')
                                        badge_url = badge.get('badge', '')
                                    elif isinstance(badge, str):
                                        badge_name = badge
                                    
                                    if badge_name:
                                        client_badges.append({
                                            "id": f"{client.lower()}_{badge_name.replace(' ', '_')}",
                                            "name": f"{badge_name} ({client})",
                                            "image": badge_url
                                        })
                        else:
                            self.logger.debug("Client badges API type unknown, skipping")
                    else:
                        self.logger.warning(f"Failed to fetch badges data, status code: {r.status}")
        except Exception as e:
            self.logger.warning(f"Error fetching badges data: {e}")

        # Fetch official Discord badges
        try:
            if self.ui_callback:
                 self.ui_callback('startup_progress', {'message': "Fetching public profile..."})
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://discord.com/api/v9/users/{user.id}/profile?type=account_popout&with_mutual_guilds=false&with_mutual_friends=false&with_mutual_friends_count=false",
                    headers=self.get_header()) as get_badge:
                    if get_badge.status == 200:
                        data = await get_badge.json()
                for badge in data.get("badges", []):
                    client_badges.append({
                        "id": badge["id"],
                        "name": badge["description"],
                        "image": f"https://cdn.discordapp.com/badge-icons/{badge['icon']}.png"
                    })
        except Exception as e:
            self.logger.warning(f"Error fetching badges: {e}")

        badges = client_badges

        self.user_data = {
            'username': user.name,
            'discriminator': user.discriminator,
            'id': str(user.id),
            'avatar': str(user.display_avatar.url) if user.display_avatar else '',
            'server_count': len(self.client.guilds) if hasattr(self.client, 'guilds') else 0,
            'friend_count': len(getattr(self.client, 'friends', [])) if hasattr(self.client, 'friends') else 0,
            'nitro_type': display,
            'badges': badges
        }

        # Send info to frontend if callback is defined
        try:
            if self.ui_callback:
                self.ui_callback('startup_progress', {'message': "Finalizing..."})
                await asyncio.sleep(0.2) # Small delay to ensure message visibility
                self.ui_callback('user_data_updated', self.user_data)
        except Exception:
            self.logger.exception("Error while calling ui_callback")

    async def _get_external_asset(self, asset_url: str, app_id: str) -> str:
        """Convert an external URL to Discord's mp: format."""
        try:
            headers = {
                'Authorization': self.config_manager.get_token(),
                'Content-Type': 'application/json'
            }
            payload = {"urls": [asset_url]}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://discord.com/api/v9/applications/{app_id}/external-assets",
                    headers=headers,
                    json=payload
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data and len(data) > 0:
                            return f"mp:{data[0]['external_asset_path']}"
                    else:
                        self.logger.error(f"External asset API error: {resp.status}")
        except Exception as e:
            self.logger.error(f"Failed to get external asset: {e}")
        return None

    async def _send_webhook(self, event_type, data):
        """Sends a webhook notification for a specific event."""
        try:
            webhooks_config = self.config_manager.get("webhooks", {})
            events_config = webhooks_config.get("events", {})
            event_config = events_config.get(event_type, {})

            if not event_config.get("enabled", False):
                return

            webhook_url = event_config.get("webhook_url", "")
            if not webhook_url:
                return
            
            embed_config = self.config_manager.get("embed", {})
            style_color = embed_config.get("color", 0x2b2d31)
            
            # Ensure color is an integer
            try:
                if isinstance(style_color, str):
                    style_color = int(style_color.lstrip('#'), 16)
                else:
                    style_color = int(style_color)
            except Exception:
                style_color = 0x2b2d31

            style_author_name = embed_config.get("author_text", "Orbyte")
            style_author_icon = embed_config.get("author_icon_url", "")
            style_footer_text = embed_config.get("footer_text", "Orbyte Notification")
            style_footer_icon = embed_config.get("footer_icon_url", "")
            style_thumb = embed_config.get("thumbnail_url", "")
            style_image = embed_config.get("image_url", "")

            embed = {
                "title": data.get("title", f"Event: {event_type}"),
                "description": data.get("description", ""),
                "color": style_color,
            }
            
            # Apply Styling
            if style_author_name:
                embed["author"] = {"name": style_author_name}
                if style_author_icon:
                    embed["author"]["icon_url"] = style_author_icon
            
            embed["footer"] = {"text": style_footer_text}
            if style_footer_icon:
                embed["footer"]["icon_url"] = style_footer_icon
                
            if style_thumb:
                embed["thumbnail"] = {"url": style_thumb}
            
            if style_image:
                embed["image"] = {"url": style_image}
            
            if "fields" in data:
                embed["fields"] = data["fields"]
                
            payload = {
                "username": style_author_name if style_author_name else "Orbyte Notifier",
                "avatar_url": style_author_icon if style_author_icon else None,
                "embeds": [embed]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as resp:
                    if resp.status not in (200, 204):
                        self.logger.warning(f"Failed to send webhook for {event_type}: {resp.status}")
        except Exception as e:
            self.logger.error(f"Error sending webhook for {event_type}: {e}")

    def set_presence(self, data):
        """
        Update the bot's presence (RPC) using discord.py-self Activity.
        data format:
        {
            'application_id': '123...', 
            'name': 'My Custom Game',
            'details': '...', 
            'state': '...', 
            'assets': {'large_image': '...', 'large_text': '...', ...},
            'timestamps': {'start': 123...},
            'buttons': [{'label': '...', 'url': '...'}]
        }
        """
        if not self.client or not self.is_running:
            return {'success': False, 'error': 'Bot not running'}

        try:
            app_id = data.get('application_id')
            if not app_id:
                return {'success': False, 'error': 'Application ID is required'}
            
            async def _set():
                # Convert external URLs to mp: format
                assets = data.get('assets', {})
                clean_assets = {}
                
                if assets.get('large_image'):
                    img = assets['large_image']
                    if img.startswith('http'):
                        converted = await self._get_external_asset(img, app_id)
                        if converted:
                            clean_assets['large_image'] = converted
                    else:
                        clean_assets['large_image'] = img
                
                if assets.get('large_text'):
                    clean_assets['large_text'] = assets['large_text']
                
                if assets.get('small_image'):
                    img = assets['small_image']
                    if img.startswith('http'):
                        converted = await self._get_external_asset(img, app_id)
                        if converted:
                            clean_assets['small_image'] = converted
                    else:
                        clean_assets['small_image'] = img
                
                if assets.get('small_text'):
                    clean_assets['small_text'] = assets['small_text']
                
                # Build activity kwargs
                activity_kwargs = {
                    'type': discord.ActivityType.playing,
                    'name': data.get('name') or 'Playing',
                    'application_id': int(app_id)
                }
                
                if data.get('details'):
                    activity_kwargs['details'] = data['details']
                if data.get('state'):
                    activity_kwargs['state'] = data['state']
                if clean_assets:
                    activity_kwargs['assets'] = clean_assets
                
                # Handle timestamps
                timestamps = data.get('timestamps', {})
                if timestamps and timestamps.get('start'):
                    start = timestamps['start']
                    if start < 1e12:
                        start = int(start * 1000)
                    activity_kwargs['timestamps'] = {'start': int(start)}
                
                # Handle buttons
                buttons = data.get('buttons')
                if buttons and isinstance(buttons, list) and len(buttons) > 0:
                    formatted_buttons = []
                    for btn in buttons[:2]:
                        label = btn.get('label')
                        url = btn.get('url')
                        if label and url:
                            formatted_buttons.append(discord.ActivityButton(label=label, url=url))
                    
                    if formatted_buttons:
                        activity_kwargs['buttons'] = formatted_buttons
                
                current_status = self.client.status
                existing_activities = self.client.activities
                custom_activity = None
                for a in existing_activities:
                    if a.type == discord.ActivityType.custom:
                        custom_activity = a
                        break
                
                new_activity = discord.Activity(**activity_kwargs)
                
                final_activities = [new_activity]
                if custom_activity:
                    final_activities.append(custom_activity)

                await self.client.change_presence(activities=final_activities, status=current_status)
            
            if self.loop:
                asyncio.run_coroutine_threadsafe(_set(), self.loop).result(timeout=15)
            
            self.logger.info("discord.py-self presence update successful")
            return {'success': True}
            
        except Exception as e:
            self.logger.error(f"Failed to set presence: {e}")
            return {'success': False, 'error': str(e)}

    def clear_presence(self):
        """Clears the bot's presence using discord.py-self."""
        if not self.client or not self.is_running:
            return {'success': False, 'error': 'Bot not running'}
        
        try:
            async def _clear():
                # Preserve current status (Online, Idle, DND)
                current_status = self.client.status

                # Preserve Custom Status (Text) - Keep only CustomActivity
                existing_activities = self.client.activities
                final_activities = []
                for a in existing_activities:
                    if a.type == discord.ActivityType.custom:
                        final_activities.append(a)
                        break
                
                await self.client.change_presence(activities=final_activities, status=current_status)
            
            self.logger.info("Presence cleared")
            return {'success': True}
        except Exception as e:
            self.logger.error(f"Failed to clear presence: {e}")
            return {'success': False, 'error': str(e)}

    def get_self_info(self):
        """Returns the current user's ID."""
        if not self.client or not self.client.user:
            return {'success': False, 'error': 'Bot not ready'}
        return {'success': True, 'id': str(self.client.user.id)}

    def get_controller_info(self):
        """Returns the Controller Bot's User ID."""
        if not self.controller_client or not self.controller_client.user_id:
            return {'success': False, 'error': 'Controller Bot not ready (or not configured)'}
        return {'success': True, 'id': str(self.controller_client.user_id)}

    def upload_image_to_discord(self, file_data, filename="image.png"):
        """
        Uploads an image to Discord (Saved Messages) and returns the URL.
        file_data: bytes
        """
        if not self.client or not self.client.user:
            return {'success': False, 'error': 'Bot not ready'}

        try:
            # Simplified upload strategy for selfbots
            async def _upload():
                import io
                f = discord.File(io.BytesIO(file_data), filename=filename)
                
                # Direct send to self (standard for discord.py-self)
                # This should automatically find/create the "Saved Messages" channel
                try:
                    if hasattr(self.client.user, 'send'):
                        msg = await self.client.user.send(file=f)
                        if msg and msg.attachments:
                            return msg.attachments[0].url
                except Exception as e:
                    self.logger.error(f"Direct send failed: {e}")
                    
                    # Fallback: Try to find the 'Saved Messages' channel manually
                    # It's a DM where recipient.id == client.user.id
                    channel = None
                    for ch in self.client.private_channels:
                        if hasattr(ch, 'recipient') and ch.recipient.id == self.client.user.id:
                            channel = ch
                            break
                    
                    if channel:
                         msg = await channel.send(file=f)
                         if msg and msg.attachments:
                            return msg.attachments[0].url
                    else:
                        raise Exception("No Saved Messages channel found and direct send failed.")
                
                return None

            if self.loop:
                future = asyncio.run_coroutine_threadsafe(_upload(), self.loop)
                url = future.result(timeout=20)
                if url:
                     return {'success': True, 'url': url}
                else:
                     return {'success': False, 'error': 'Upload successful but no URL returned'}
            
            return {'success': False, 'error': 'Loop not available'}

        except Exception as e:
            self.logger.error(f"Failed to upload image: {e}")
            return {'success': False, 'error': str(e)}

    def shutdown(self):
        """
        Arrête proprement le bot et ferme la boucle event.
        """
        if self.loop and self.is_running and not self.loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(self.client.close(), self.loop)
            except Exception:
                pass

    async def run_script(self, script_content: str, filename: str = "script.py"):
        """
        Dynamically executes a Python script.
        - Scripts adding commands or listeners stay "active" until manually stopped.
        - Captures stdout/stderr in REAL TIME.
        - Exposes 'bot' (wrapped), 'discord', 'asyncio' to the script.
        """
        if not self.ui_callback:
            return

        # Prepare global monitoring
        self.ui_callback('script_start', {'filename': filename})
        
        # If this script is already running, stop the previous instance
        if filename in self.running_tasks:
             await self.stop_script(filename)

        class RealtimeOutput:
            def __init__(self, callback, fname):
                self.callback = callback
                self.fname = fname
            
            def write(self, text):
                if text:
                    self.callback('script_output', {'filename': self.fname, 'content': text})
            
            def flush(self):
                pass
        
        realtime_stream = RealtimeOutput(self.ui_callback, filename)
        
        class ScriptBotWrapper:
            def __init__(self, bot):
                self._bot = bot
            
            def __getattr__(self, name):
                return getattr(self._bot, name)
            
            def event(self, coroutine=None):
                if coroutine is not None:
                    self._bot.add_listener(coroutine)
                    return coroutine
                
                def decorator(func):
                    self._bot.add_listener(func)
                    return func
                return decorator

        # Function to capture current listeners state
        def get_all_listeners(bot):
            snapshot = set()
            for event_name, funcs in bot.extra_events.items():
                for f in funcs:
                    snapshot.add((event_name, f))
            return snapshot

        # Snapshots before execution
        commands_before = {cmd.name for cmd in self.client.commands} if self.client else set()
        listeners_before = get_all_listeners(self.client) if self.client else set()
        
        # Context for the script
        script_globals = {
            'bot': ScriptBotWrapper(self.client),
            'discord': discord,
            'asyncio': asyncio,
            'commands': commands,
            'ctx': None,
            'print': lambda *args, **kwargs: print(*args, file=realtime_stream, **kwargs)
        }

        try:
            with contextlib.redirect_stdout(realtime_stream), contextlib.redirect_stderr(realtime_stream):
                # Execute the script
                exec(script_content, script_globals)
                
                # Check for new commands
                commands_after = {cmd.name for cmd in self.client.commands} if self.client else set()
                new_commands = commands_after - commands_before
                
                # Check for new listeners
                listeners_after = get_all_listeners(self.client) if self.client else set()
                new_listeners = listeners_after - listeners_before

                active_components = []
                
                if new_commands:
                    self.script_commands[filename] = list(new_commands)
                    active_components.append(f"Commands: {', '.join(new_commands)}")

                if new_listeners:
                    self.script_listeners[filename] = list(new_listeners)
                    active_components.append(f"Listeners: {len(new_listeners)}")

                if active_components:
                    self.ui_callback('script_output', {
                        'filename': filename, 
                        'content': f"\n[System] Registered {'; '.join(active_components)}.\n[System] Script is now active."
                    })
                    
                    # Create a keep-alive task
                    async def keep_alive():
                        try:
                            while True:
                                await asyncio.sleep(3600)
                        except asyncio.CancelledError:
                            raise
                    
                    task = asyncio.create_task(keep_alive())
                    self.running_tasks[filename] = task
                    await task
                else:
                    # No commands or listeners - check for async code
                    has_async_code = 'await ' in script_content or 'async def' in script_content
                    
                    if has_async_code:
                        # Wrap in async function
                        wrapped_code = "import asyncio\nasync def _script_main():\n"
                        for line in script_content.splitlines():
                            wrapped_code += f"    {line}\n"
                        wrapped_code += "\n_task = asyncio.create_task(_script_main())"
                        
                        exec(wrapped_code, script_globals)
                        
                        if '_task' in script_globals:
                            task = script_globals['_task']
                            self.running_tasks[filename] = task
                            await task
                    
                    self.ui_callback('script_output', {
                        'filename': filename, 
                        'content': "\n[System] Script executed successfully."
                    })
            
            self.ui_callback('script_end', {'filename': filename})

        except asyncio.CancelledError:
            self.ui_callback('script_output', {'filename': filename, 'content': "\n[System] Script stopped by user."})
            self.ui_callback('script_end', {'filename': filename})
        except Exception as e:
            tb = traceback.format_exc()
            self.ui_callback('script_error', {'filename': filename, 'error': tb})
            self.ui_callback('script_end', {'filename': filename})
        finally:
            self.running_tasks.pop(filename, None)

    async def stop_script(self, filename: str):
        """Stops a specific script and cleans up commands AND listeners."""
        messages = []

        # 1. Cleanup Commands
        if hasattr(self, 'script_commands') and filename in self.script_commands:
            removed_cmds = []
            for cmd_name in self.script_commands[filename]:
                cmd = self.client.get_command(cmd_name)
                if cmd:
                    self.client.remove_command(cmd_name)
                    removed_cmds.append(cmd_name)
            
            if removed_cmds:
                messages.append(f"Removed commands: {', '.join(removed_cmds)}")
            del self.script_commands[filename]

        # 2. Cleanup Listeners
        if hasattr(self, 'script_listeners') and filename in self.script_listeners:
            count = 0
            for (event_name, func) in self.script_listeners[filename]:
                try:
                    self.client.remove_listener(func, event_name)
                    count += 1
                except Exception as e:
                    self.logger.error(f"Failed to remove listener {event_name}: {e}")
            
            if count > 0:
                messages.append(f"Removed {count} listeners")
            del self.script_listeners[filename]
        
        # 3. Cancel Task
        if filename in self.running_tasks:
            task = self.running_tasks[filename]
            if not task.done():
                task.cancel()
                messages.append("Stopping execution...")
        
        if messages and self.ui_callback:
             self.ui_callback('script_output', {
                'filename': filename, 
                'content': "\n[System] " + "; ".join(messages)
            })
