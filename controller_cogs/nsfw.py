from controller_commands import CommandGroup, Option, send_smart_embed, get_arg, get_embed_style
import datetime
import discord

nsfw = CommandGroup("nsfw", "NSFW related commands")

async def IsNsfw(client, interaction):
    channel_id = interaction.get('channel_id')
    channel = client.selfbot.get_channel(int(channel_id))
    
    if not channel:
        return False
        
    # Check if risky mode is on
    if client.config_manager.get("risky_mode"):
        return True

    # Safely check is_nsfw
    is_nsfw = False
    if hasattr(channel, 'is_nsfw'):
        if callable(channel.is_nsfw):
            is_nsfw = channel.is_nsfw()
        else:
            is_nsfw = channel.is_nsfw
    elif isinstance(channel, discord.DMChannel):
        if client.config_manager.get("risky_mode"):
            is_nsfw = True
    return is_nsfw

async def fetch_and_send_nsfw(client, interaction, endpoint_type):
    """
    Helper to fetch an image from nekobot and send it as a styled embed.
    """
    # 1. Check NSFW/Risky Mode
    if not await IsNsfw(client, interaction):
        await client.send_response(interaction, "⚠️ Risky mode is disabled or this channel is not NSFW. Enable risky mode in settings or use an NSFW channel.", ephemeral=True)
        return

    # 2. Defer (as fetching might take a moment)
    await client.defer(interaction)

    try:
        # 3. Fetch Image
        url = f"https://nekobot.xyz/api/image?type={endpoint_type}"
        async with client.session.get(url) as resp:
            if resp.status != 200:
                await client.followup(interaction, "❌ API Error: Could not fetch image.")
                return
            
            data = await resp.json()
            image_url = data.get("message")
            
            if not image_url:
                await client.followup(interaction, "❌ API Error: No image found.")
                return

            # 4. Build Embed with Style
            style = get_embed_style(client)
            
            embed = discord.Embed(
                color=style["color"],
                timestamp=None # No timestamp for images usually cleaner, or add fetch time?
            )
            
            # Author
            if style["author_icon_url"]:
                embed.set_author(name=f"{style['author_text']}", icon_url=style["author_icon_url"])
            else:
                embed.set_author(name=f"{style['author_text']}")
                
            embed.set_footer(text=style["footer_text"], icon_url=style["footer_icon_url"] if style["footer_icon_url"] else None)
            
            # embed.set_thumbnail(url=f"{style['thumbnail_url']}")

            embed.set_image(url=image_url)

            await send_smart_embed(client, interaction, embed, forward_delay=2.0, skip_thumb=True)

    except Exception as e:
        await client.followup(interaction, f"❌ Error: {e}")

# === Commands ===

@nsfw.command("ass", "Ass image (+18)")
async def nsfw_ass(client, interaction):
    await fetch_and_send_nsfw(client, interaction, "ass")

@nsfw.command("hentai", "Hentai image (+18)")
async def nsfw_hentai(client, interaction):
    await fetch_and_send_nsfw(client, interaction, "hentai")

@nsfw.command("anal", "Anal image (+18)")
async def nsfw_anal(client, interaction):
    await fetch_and_send_nsfw(client, interaction, "anal")

@nsfw.command("pussy", "Pussy image (+18)")
async def nsfw_pussy(client, interaction):
    await fetch_and_send_nsfw(client, interaction, "pussy")

@nsfw.command("boobs", "Boobs image (+18)")
async def nsfw_boobs(client, interaction):
    await fetch_and_send_nsfw(client, interaction, "boobs")

@nsfw.command("feet", "Feet image (+18)")
async def nsfw_feet(client, interaction):
    await fetch_and_send_nsfw(client, interaction, "feet")

@nsfw.command("gifs", "NSFW gifs (+18)")
async def nsfw_gifs(client, interaction):
    await fetch_and_send_nsfw(client, interaction, "pgif")

@nsfw.command("thighs", "Thighs image (+18)")
async def nsfw_thighs(client, interaction):
    await fetch_and_send_nsfw(client, interaction, "thigh")

@nsfw.command("blowjob", "Blowjob image (+18)")
async def nsfw_blowjob(client, interaction):
    await fetch_and_send_nsfw(client, interaction, "blowjob")

@nsfw.command("gonewild", "Gonewild image (+18)")
async def nsfw_gonewild(client, interaction):
    await fetch_and_send_nsfw(client, interaction, "gonewild")