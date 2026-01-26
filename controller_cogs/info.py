from controller_commands import CommandGroup, Option, send_smart_embed, get_arg, get_embed_style
import datetime
import discord

info = CommandGroup("info", "Info related commands")

async def info_autocomplete(client, interaction):
    """
    Autocomplete handler for searching servers and users.
    """
    
    choices = []
    
    try:
        current_val = ""
        focused_option = ""
        
        for opt in interaction['data'].get('options', []):
            if opt.get('type') == 1:
                for sub_opt in opt.get('options', []):
                    if sub_opt.get('focused'):
                        current_val = sub_opt['value']
                        focused_option = sub_opt['name']
                        break
            elif opt.get('focused'):
                current_val = opt['value']
                focused_option = opt['name']
                break
                
        current_val = str(current_val).lower()
                
        if client.selfbot and client.selfbot.is_ready():
            if focused_option == "server":
                matches = []
                for g in client.selfbot.guilds:
                    if current_val in g.name.lower() or current_val in str(g.id):
                        matches.append(g)
                
                for g in matches[:25]:
                    choices.append({
                        "name": g.name,
                        "value": str(g.id)
                    })
            
            elif focused_option == "user":
                matches = []
                count = 0
                
                # Verify friends attribute exists
                if hasattr(client.selfbot, 'friends'):
                    for rel in client.selfbot.friends:
                        u = rel.user
                        if current_val in u.name.lower() or current_val in str(u.id):
                            matches.append(u)
                            count += 1
                
                if count < 25:
                    for u in client.selfbot.users:
                        if u not in matches and (current_val in u.name.lower() or current_val in str(u.id)):
                            matches.append(u)
                            count += 1
                            if count >= 25: 
                                break
                
                for u in matches[:25]:
                    choices.append({
                        "name": f"{u.name} ({u.id})",
                        "value": str(u.id)
                    })
        else:
            logger.warning("Selfbot not ready during autocomplete")

    except Exception as e:
        logger.error(f"Autocomplete Error: {e}")

    # Always attempt to send result
    try:
        await client.send_autocomplete_result(interaction, choices)
    except Exception as e:
        logger.error(f"Failed to send autocomplete result: {e}")

@info.command(
    name="server", 
    description="Get information about a server",
    options=[
        Option("server", "Name or ID of the server (Autocomplete)", Option.STRING, required=False, autocomplete=True)
    ],
    autocomplete=info_autocomplete
)
async def info_server(client, interaction):
    """
    Handler for /info server
    """
    # Preliminary Checks
    if not client.selfbot or not client.selfbot.is_ready():
        await client.send_response(interaction, "❌ Selfbot is not connected.", ephemeral=True)
        return

    await client.defer(interaction)

    try:
        # Resolve Guild
        target_guild_id = get_arg(interaction, "server")
        guild = None

        if target_guild_id:
            # Case A: User selected a specific server
            try:
                gid = int(target_guild_id)
                guild = client.selfbot.get_guild(gid)
                if not guild:
                    try: guild = await client.selfbot.fetch_guild(gid)
                    except: pass
            except:
                await client.followup(interaction, "❌ Invalid Server ID provided.")
                return
        else:
            # Case B: Use current context
            guild_id_raw = interaction.get('guild_id')
            if guild_id_raw:
                gid = int(guild_id_raw)
                guild = client.selfbot.get_guild(gid)
                if not guild:
                    try: guild = await client.selfbot.fetch_guild(gid)
                    except: pass
        
        if not guild:
            await client.followup(interaction, "❌ Could not find the specified server (or not in a server).")
            return

        # Prepare Data
        created_at = guild.created_at.strftime("%A, %B %d, %Y %I:%M %p")
        owner = f"{guild.owner.name} ({guild.owner.id})" if guild.owner else "Unknown"
        vanity = f"https://discord.gg/{guild.vanity_url_code}" if guild.vanity_url_code else "None"
        mfa = "required" if guild.mfa_level else "not required"
        verification = str(guild.verification_level).lower()
        
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        roles_count = len(guild.roles) if hasattr(guild, 'roles') else "N/A"
        
        lines = [
            "",
            f"**Name**: {guild.name}",
            f"**ID**: {guild.id}",
            f"**Created at**: {created_at}",
            f"**Owner**: {owner}",
            f"**Total members**: {guild.member_count}",
            f"**Roles**: {roles_count}",
            f"**Total boosts**: {guild.premium_subscription_count}",
            f"**Boost level**: {guild.premium_tier}",
            f"**Vanity**: {vanity}",
            f"**Text channels**: {text_channels}",
            f"**Voice channels**: {voice_channels}",
            f"**Categories**: {categories}",
            f"**Verification level**: {verification}",
            f"**MFA**: 2FA {mfa}",
        ]
        content = "\n".join(lines)

        # Load Styling
        style = get_embed_style(client)
        author_text = style["author_text"]
        author_icon = style["author_icon_url"]
        thumbnail_url = style["thumbnail_url"]
        footer_text = style["footer_text"]
        footer_icon = style["footer_icon_url"]
        color = style["color"]

        # Build and Send Embed
        embed = discord.Embed(
            title=author_text,
            description=content,
            color=color,
            timestamp=None
        )
        
        if author_icon:
            embed.set_author(name="Server information", icon_url=author_icon)
        else:
            embed.set_author(name="Server information")
            
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
            
        embed.set_footer(text=footer_text, icon_url=footer_icon if footer_icon else None)

        await send_smart_embed(client, interaction, embed)

    except Exception as e:
        await client.followup(interaction, f"❌ Error fetching server info: {e}")

@info.command(
    name="user",
    description="Get information about a user",
    options=[
        Option("user", "Name of the user (Autocomplete)", Option.STRING, required=False, autocomplete=True),
        Option("user_id", "ID of the user", Option.STRING, required=False)
    ],
    autocomplete=info_autocomplete
)
async def info_user(client, interaction):
    """
    Handler for /info user.
    Retrieves detailed information about a Discord user.
    """
    # Preliminary Checks
    if not client.selfbot or not client.selfbot.is_ready():
        await client.send_response(interaction, "❌ Selfbot is not connected.", ephemeral=True)
        return

    await client.defer(interaction)
    
    try:
        # Resolve User
        target_user_opt = get_arg(interaction, "user")
        target_userid_opt = get_arg(interaction, "user_id")
        
        user = None

        try:
            uid = None
            if target_userid_opt:
                uid = int(target_userid_opt)
            elif target_user_opt:
                uid = int(target_user_opt)
            else:
                uid = int(interaction.get('user_id') or interaction.get('member', {}).get('user', {}).get('id', 0))

            if uid:
                user = client.selfbot.get_user(uid)
                if not user:
                    user = await client.selfbot.fetch_user(uid)
        except:
            pass
        
        if not user:
            await client.followup(interaction, "❌ Could not find the specified user.")
            return
        
        user_profile = None
        try:
            user_profile = await user.profile()
        except:
            pass

        mutual_friends = []
        mutual_guilds = []

        try:
            if hasattr(user, 'mutual_friends'):
                mutual_friends = user.mutual_friends() 
            elif user_profile and hasattr(user_profile, 'mutual_friends'):
                mutual_friends = user_profile.mutual_friends
            
            if hasattr(user, 'mutual_guilds'):
                mutual_guilds = user.mutual_guilds()
            elif user_profile and hasattr(user_profile, 'mutual_guilds'):
                mutual_guilds = user_profile.mutual_guilds
        except:
            pass

        history = []
        last_seen_ts = None
        
        if hasattr(client.selfbot, 'get_user_history'):
            history = client.selfbot.get_user_history(user.id)
        
        if hasattr(client.selfbot, 'get_last_seen'):
            last_seen_ts = client.selfbot.get_last_seen(user.id)
        
        name_safe = discord.utils.escape_markdown(user.name)
        username = f"{name_safe}#{user.discriminator}" if user.discriminator != '0' else name_safe
        user_id = str(user.id)
        created_ts = int(user.created_at.timestamp())
        created_at = f"<t:{created_ts}:f> (<t:{created_ts}:R>)"
        
        is_bot = "Yes" if user.bot else "No"
        
        is_friend = "No"
        try:
            for rel in client.selfbot.friends:
                if rel.user.id == user.id:
                    is_friend = "Yes"
                    break
        except:
            pass

        bio_raw = (user_profile.bio if user_profile and user_profile.bio else "None")
        bio = discord.utils.escape_markdown(bio_raw)

        if mutual_friends:
            mf_names = [discord.utils.escape_markdown(f.name) for f in mutual_friends]
            mutual_friends_display = ", ".join(mf_names)
            if len(mutual_friends_display) > 1000:
                mutual_friends_display = mutual_friends_display[:997] + "..."
        else:
            mutual_friends_display = "None"
        
        if mutual_guilds:
            mg_list = []
            for mg in mutual_guilds:
                guild_obj = client.selfbot.get_guild(mg.id)
                if guild_obj:
                     guild_name_safe = discord.utils.escape_markdown(guild_obj.name)
                     mg_list.append(f"{guild_name_safe} ({guild_obj.member_count} members)")
                else:
                     mg_list.append(f"Server ID {mg.id}")
            
            mutual_server_display = ", ".join(mg_list)
            if len(mutual_server_display) > 1000:
                mutual_server_display = mutual_server_display[:997] + "..."
        else:
            mutual_server_display = "None"
        
        connections = "None"
        if user_profile and hasattr(user_profile, 'connections') and user_profile.connections:
            accs = [f"{acc.type.name} - {discord.utils.escape_markdown(acc.name)}" for acc in user_profile.connections]
            if accs:
                connections = " | ".join(accs)
        
        last_seen_str = "Unknown"
        if last_seen_ts:
            last_seen_str = f"<t:{int(last_seen_ts)}:f> (<t:{int(last_seen_ts)}:R>)"
        else:
            member = None
            for g in client.selfbot.guilds:
                m = g.get_member(user.id)
                if m:
                    member = m
                    break
            
            if member and member.status != discord.Status.offline:
                last_seen_str = "Online Now"

        history_str = "None"
        if history:
            lines = []
            for h in history[:3]:
                dt = datetime.datetime.fromtimestamp(h['timestamp'])
                date_str = dt.strftime("%Y-%m-%d")
                safe_username = discord.utils.escape_markdown(h['username'])
                lines.append(f"{safe_username} ({date_str})")
            history_str = ", ".join(lines)
            
        lines = [
            "",
            f"**User**: {username}",
            f"**ID**: {user_id}",
            f"**Bio**: {bio}",
            f"**Mutual friends**: {mutual_friends_display}",
            f"**Mutual server**: {mutual_server_display}",
            f"**Created date**: {created_at}",
            f"**Is friend**: {is_friend}",
            f"**Is bot**: {is_bot}",
            f"**Connection**: {connections}",
            f"**Last seen**: {last_seen_str}",
            f"**Username history**: {history_str}"
        ]
        content = "\n".join(lines)

        style = get_embed_style(client)

        embed = discord.Embed(
            title=style["author_text"],
            description=content,
            color=style["color"],
            timestamp=None
        )
        
        if style["author_icon_url"]:
            embed.set_author(name="User information", icon_url=style["author_icon_url"])
        else:
            embed.set_author(name="User information")
            
        if style["thumbnail_url"]:
            embed.set_thumbnail(url=style["thumbnail_url"])
        elif user.display_avatar:
             embed.set_thumbnail(url=user.display_avatar.url)
            
        embed.set_footer(text=style["footer_text"], icon_url=style["footer_icon_url"] if style["footer_icon_url"] else None)

        await send_smart_embed(client, interaction, embed)
    except Exception as e:
        await client.followup(interaction, f"❌ Error fetching user info: {e}")


@info.command(
    name="roblox",
    description="Get information about a Roblox user",
    options=[
        Option("username", "The Roblox username to search for", Option.STRING, required=True)
    ] 
)
async def roblox_command(client, interaction):
    """
    Handler for /roblox.
    Fetches Roblox user data including ID, bio, and creation date.
    """
    await client.defer(interaction)
    
    raw_username = get_arg(interaction, "username")
    if not raw_username:
        await client.followup(interaction, "❌ Please provide a username.")
        return
    
    try:
        payload = {
            "usernames": [raw_username],
            "excludeBannedUsers": False
        }
        
        user_id = None
        display_name = None
        username = None
        
        async with client.session.post("https://users.roblox.com/v1/usernames/users", json=payload) as r:
            if r.status != 200:
                await client.followup(interaction, f"❌ Roblox API Error (User Search): {r.status}")
                return
            
            data = await r.json()
            if not data.get("data"):
                await client.followup(interaction, f"❌ No Roblox user found with name `{raw_username}`.")
                return
                
            user_data = data["data"][0]
            user_id = user_data.get("id")
            display_name = user_data.get("displayName")
            username = user_data.get("name")

        if not user_id:
            await client.followup(interaction, "❌ Could not resolve User ID.")
            return

        created_at_str = None
        description = None
        is_banned = False
        
        async with client.session.get(f"https://users.roblox.com/v1/users/{user_id}") as r:
            if r.status == 200:
                p_data = await r.json()
                created_at_str = p_data.get("created")
                description = p_data.get("description", "")
                is_banned = p_data.get("isBanned", False)
            else:
                pass

        followers_count = "Unknown"
        async with client.session.get(f"https://friends.roblox.com/v1/users/{user_id}/followers/count") as r:
            if r.status == 200:
                f_data = await r.json()
                followers_count = f_data.get("count", 0)

        avatar_url = None
        try:
            async with client.session.get(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=420x420&format=Png&isCircular=false") as r:
                if r.status == 200:
                    t_data = await r.json()
                    if t_data.get("data"):
                        avatar_url = t_data["data"][0].get("imageUrl")
        except:
            pass

        created_display = "Unknown"
        if created_at_str:
            try:
                dt = datetime.datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                ts = int(dt.timestamp())
                created_display = f"<t:{ts}:D> (<t:{ts}:R>)"
            except:
                created_display = created_at_str

        if not description:
            description = "None"
        elif len(description) > 500:
            description = description[:497] + "..."
        
        description = discord.utils.escape_markdown(description)

        status_str = "Active"
        if is_banned:
            status_str = "🚫 Banned"

        lines = [
            "",
            f"**Display Name**: {display_name}",
            f"**Username**: [{username}](https://www.roblox.com/users/{user_id}/profile)",
            f"**ID**: {user_id}",
            f"**Followers**: {followers_count}",
            f"**Created**: {created_display}",
            f"**Status**: {status_str}",
            "",
            f"**Bio**:\n{description}"
        ]
        content = "\n".join(lines)

        style = get_embed_style(client)
        
        embed = discord.Embed(
            title=style["author_text"],
            description=content,
            color=style["color"]
        )
        
        if style["author_icon_url"]:
            embed.set_author(name="Roblox User Information", icon_url=style["author_icon_url"])
        else:
            embed.set_author(name="Roblox User Information")
            
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        elif style["thumbnail_url"]:
             embed.set_thumbnail(url=style["thumbnail_url"])
        embed.set_footer(text=style["footer_text"], icon_url=style["footer_icon_url"] if style["footer_icon_url"] else None)

        await send_smart_embed(client, interaction, embed)

    except Exception as e:
        await client.followup(interaction, f"❌ Error fetching Roblox user: {e}")
