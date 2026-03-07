import discord
import re
import time
import aiohttp
import asyncio
import random
from datetime import datetime, timezone

class MessageHandler:
    """
    Handles message events (on_message, on_message_delete, on_reaction_add)
    to keep BotWorker clean.
    """
    def __init__(self, worker):
        self.worker = worker
        self.nitro_regex = re.compile(r"(?:discord\.gift/|discord(?:app)?\.com/gifts/)([a-zA-Z0-9]{16,24})")

    async def handle_message(self, message):
        """
        Main entry point for on_message event.
        """
        await self._handle_nitro_sniper(message)
        await self._handle_giveaway_sniper(message)
        self._log_activity_stats(message)
        await self._handle_notifications(message)

    async def _handle_nitro_sniper(self, message):
        """
        Checks for Nitro gift codes and attempts to claim them.
        """
        if not self.worker.config_manager.get("nitro_sniper", False):
            return

        if message.author == self.worker.client.user:
            return

        search = self.nitro_regex.search(message.content)
        if search:
            code = search.group(1)
            start_time = time.perf_counter()
            
            headers = self.worker.get_header()
            url = f"https://discord.com/api/v9/entitlements/gift-codes/{code}/redeem"
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json={'channel_id': message.channel.id}) as resp:
                        latency = (time.perf_counter() - start_time) * 1000
                        
                        if resp.status == 200:
                            self.worker.log_activity(f"Sniper: Claimed {code} in {latency:.2f}ms")
                            self.worker.logger.info(f"🚀 Nitro Sniper: Claimed code {code} in {latency:.2f}ms")
                            if self.worker.ui_callback:
                                self.worker.ui_callback('sniper_log', {'code': code, 'status': 'claimed', 'time': f"{latency:.2f}ms"})
                            
                            await self.worker._send_webhook("nitro_snipes", {
                                "title": "🚀 Nitro Sniper: Claimed!",
                                "description": f"**Code:** `{code}`\n**Time:** `{latency:.2f}ms`\n**Server:** {message.guild.name if message.guild else 'DM'}",
                                "color": 0x57F287,
                            })

                        elif resp.status == 400: # Unknown Gift
                            self.worker.log_activity(f"Sniper: Invalid {code}")
                            self.worker.logger.info(f"💥 Nitro Sniper: Invalid code {code} ({latency:.2f}ms)")
                            if self.worker.ui_callback:
                                self.worker.ui_callback('sniper_log', {'code': code, 'status': 'invalid', 'time': f"{latency:.2f}ms"})
                            
                            # Webhook: Nitro Invalid
                            await self.worker._send_webhook("nitro_snipes", {
                                "title": "💥 Nitro Sniper: Invalid Code",
                                "description": f"**Code:** `{code}`\n**Time:** `{latency:.2f}ms`\n**Status:** Invalid/Unknown Gift",
                                "color": 0xED4245, # Red
                            })

                        elif resp.status == 429: # Ratelimit
                            self.worker.log_activity(f"Sniper: RateLimited {code}")
                            self.worker.logger.warning(f"⏳ Nitro Sniper: RateLimited on {code}")
                            
                            await self.worker._send_webhook("nitro_snipes", {
                                "title": "⏳ Nitro Sniper: Rate Limited",
                                "description": f"**Code:** `{code}`",
                                "color": 0xFEE75C, # Yellow
                            })

                        else:
                            self.worker.log_activity(f"Sniper: Failed {code} ({resp.status})")
                            self.worker.logger.info(f"❓ Nitro Sniper: Failed {code} - Status {resp.status}")
                            
                            await self.worker._send_webhook("nitro_snipes", {
                                "title": "❓ Nitro Sniper: Failed",
                                "description": f"**Code:** `{code}`\n**Status Code:** `{resp.status}`",
                                "color": 0xED4245, # Red
                            })

            except Exception as e:
                 self.worker.logger.error(f"Sniper Error: {e}")

    async def _handle_giveaway_sniper(self, message):
        """
        Checks for Giveaway messages and attempts to join them.
        """
        if not self.worker.config_manager.get("giveaway_sniper", False):
            return

        giveaway_config = {
            294882584201003009: ["enter-giveaway"], # GiveawayBot
            1341497034326147083: ["participate"], # Mee6 Esport Bot on War Thunder Esport server
            1229067680716427335: ["giveaways:"], # Dyno
            318312854816161792: ["giveaway:"] # Draftbot
        }

        if message.author.id not in giveaway_config:
            return

        allowed_ids = giveaway_config[message.author.id]
        blacklisted_words = ['ban', 'banned', 'timeout', 'mute', 'selfbot']
        
        if not message.embeds:
            return
        
        embed = message.embeds[0]
        embed_dict = embed.to_dict()
        
        description = embed_dict.get('description', '').lower()
        title = embed_dict.get('title', '').lower()
        footer = embed_dict.get('footer', {}).get('text', '').lower()

        if any(word in title for word in blacklisted_words):
            return
        
        if 'ended' in footer or 'winner' in title or description.strip().startswith('ended') or 'ended' in title:
            return

        if not message.components:
            return

        try:
            for row in message.components:
                for component in row.children:
                    if component.type == discord.ComponentType.button and any(component.custom_id.startswith(prefix) for prefix in allowed_ids):
                        start_time = time.perf_counter()                            
                        
                        await asyncio.sleep(random.uniform(3, 10)) 
                        await component.click()
                        
                        latency = (time.perf_counter() - start_time) * 1000
                        server_name = message.guild.name if message.guild else 'DM'
                        
                        self.worker.log_activity(f"Giveaway Joined: {server_name}")
                        self.worker.logger.info(f"🎉 Giveaway Sniper: Joined giveaway in {server_name} ({latency:.2f}ms)")
                        
                        prize = embed_dict.get('title', 'Unknown Prize')
                        if self.worker.ui_callback:
                            self.worker.ui_callback('giveaway_log', {
                                'prize': prize,
                                'server': server_name, 
                                'status': 'joined', 
                                'time': f"{latency:.2f}ms",
                                'guild_id': str(message.guild.id) if message.guild else '0',
                                'channel_id': str(message.channel.id),
                                'message_id': str(message.id)
                            })
                            
                        # Webhook Notification
                        await self.worker._send_webhook("giveaways", {
                            "title": "🎉 Giveaway Joined",
                            "description": f"**Server:** {server_name}\n**Channel:** {message.channel.mention}\n**Prize:** {prize}\n**Time:** `{latency:.2f}ms`\n\n[Jump to Giveaway]({message.jump_url})",
                            "color": 0xF1C40F,
                        })
                        
                        return # Successfully joined, exit method
                            
        except Exception as e:
            self.worker.logger.error(f"Giveaway Sniper Error: {e}")
    

    def _log_activity_stats(self, message):
        """
        Logs simple activity stats to the database.
        """
        bot = self.worker.client
        
        # Log Activity: Message Sent
        if bot.user == message.author:
            self.worker.log_activity('message_sent')

        # Log Activity: Ping Received
        if bot.user in message.mentions:
            self.worker.log_activity('ping_received')

    async def _handle_notifications(self, message):
        """
        Handles pings, mentions, and ghost ping detection logic.
        """
        bot = self.worker.client
        
        # Handle Mention Everyone/Here
        if message.mention_everyone and message.author != message.guild.me:
            if self.worker.ui_callback:
                self.worker.ui_callback('ping_received', {
                    'user': str(message.author.name),
                    'server_name': str(message.guild.name),
                    'content': message.content,
                    'guild_id': str(message.guild.id),
                    'channel_id': str(message.channel.id),
                    'message_id': str(message.id)
                })
            
            # Webhook: Ping Received (Everyone/Here)
            await self.worker._send_webhook("pings", {
                "title": "🔔 Ping Received (Everyone/Here)",
                "description": f"**Server:** {message.guild.name}\n**Channel:** {message.channel.mention}\n**Author:** {message.author.mention} (`{message.author.id}`)\n**Content:** {message.content}\n\n[Jump to Message]({message.jump_url})",
                "color": 0x5865F2,
            })

        # Handle Direct Mentions
        if message.guild and message.guild.me in message.mentions and message.author != message.guild.me:
            if self.worker.ui_callback:
                # Format content to be readable (replace IDs with names)
                message_content = message.content.replace(
                    f"<@{message.guild.me.id}>", f"@{message.guild.me.name}"
                ).strip()
                for user in message.mentions:
                    if user != message.guild.me:
                        message_content = message_content.replace(
                            f"<@{user.id}>", f"@{user.name}"
                        )
                
                self.worker.ui_callback('ping_received', {
                    'user': str(message.author.name),
                    'server_name': str(message.guild.name),
                    'content': message_content,
                    'guild_id': str(message.guild.id),
                    'channel_id': str(message.channel.id),
                    'message_id': str(message.id)
                })

            # Webhook: Ping Received
            await self.worker._send_webhook("pings", {
                "title": "🔔 Ping Received",
                "description": f"**Server:** {message.guild.name}\n**Channel:** {message.channel.mention}\n**Author:** {message.author.mention} (`{message.author.id}`)\n**Content:** {message.content}\n\n[Jump to Message]({message.jump_url})",
                "color": 0x5865F2,
            })

        # Handle Role Mentions
        if message.guild and message.author != message.guild.me:
            mentioned_roles = [role for role in message.role_mentions if role in message.guild.me.roles]
            if mentioned_roles:
                role_names = ", ".join([role.name for role in mentioned_roles])
                if self.worker.ui_callback:
                    message_content = message.content
                    for role in mentioned_roles:
                         message_content = message_content.replace(f"<@&{role.id}>", f"@{role.name}").strip()
                    
                    self.worker.ui_callback('ping_received', {
                        'user': str(message.author.name),
                        'server_name': str(message.guild.name),
                        'content': message_content,
                        'guild_id': str(message.guild.id),
                        'channel_id': str(message.channel.id),
                        'message_id': str(message.id)
                    })

                # Webhook: Role Ping Received
                await self.worker._send_webhook("pings", {
                    "title": f"🔔 Role Ping Received ({role_names})",
                    "description": f"**Server:** {message.guild.name}\n**Channel:** {message.channel.mention}\n**Author:** {message.author.mention} (`{message.author.id}`)\n**Content:** {message.content}\n\n[Jump to Message]({message.jump_url})",
                    "color": 0x5865F2,
                })

    async def handle_message_delete(self, message):
        """
        Handles ghost ping detection on message delete.
        """
        # Ghost Ping Detection
        if message.guild and message.author != message.guild.me:
            is_mentioned = message.guild.me in message.mentions
            is_role_mentioned = any(role in message.guild.me.roles for role in message.role_mentions)
            
            if is_mentioned or is_role_mentioned:
                time_diff = (datetime.now(timezone.utc) - message.created_at).total_seconds()
                
                if time_diff < 300:
                    await self.worker._send_webhook("ghostpings", {
                        "title": "👻 Ghost Ping Detected",
                        "description": f"**Server:** {message.guild.name}\n**Channel:** {message.channel.mention}\n**Author:** {message.author.mention} (`{message.author.id}`)\n**Content:** {message.content}",
                        "color": 0x99AAB5,
                    })

    async def handle_reaction_add(self, reaction, user):
        """
        Handles reaction logs.
        """
        bot = self.worker.client
        if user == bot.user:
             self.worker.log_activity('reaction_added')
