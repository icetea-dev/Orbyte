from controller_commands import controller_command, Option
from controller_commands import controller_command, Option
import datetime

@controller_command(
    name="embed", 
    description="Send a custom embed via your Selfbot",
    options=[
        Option("content", "Main text content of the embed", Option.STRING, required=False),
        Option("title", "Title of the embed (Optional)", Option.STRING, required=False),
        Option("image_url", "URL of an image/thumbnail (Optional)", Option.STRING, required=False),
        Option("thumb", "Use custom thumbnail from settings? (Default: False)", Option.BOOLEAN, required=False),
        Option("author_name", "Override author name (Optional)", Option.STRING, required=False),
        Option("delete_after", "Delete after N seconds (Optional)", Option.INTEGER, required=False)
    ]
)
async def embed_command(client, interaction):
    """
    Handler for /embed.
    
    This command sends a custom embed using the settings from the configuration.
    It supports sending directly via the Controller or forwarding through the Selfbot.
    """
    from controller_commands import get_arg, get_embed_style
    
    if not client.selfbot or not client.selfbot.is_ready():
        await client.send_response(interaction, "❌ Selfbot is not connected.", ephemeral=True)
        return

    forwarding_enabled = client.config_manager.get("discord.controller_forwarding", False)
    is_ephemeral = not forwarding_enabled

    await client.defer(interaction, ephemeral=is_ephemeral)
    
    content = get_arg(interaction, "content")
    title = get_arg(interaction, "title")
    image_url = get_arg(interaction, "image_url")
    use_thumb = get_arg(interaction, "thumb", default=False)
    custom_author_name = get_arg(interaction, "author_name")
    delete_seconds = get_arg(interaction, "delete_after")

    style = get_embed_style(client)

    import discord
    embed = discord.Embed(
        description=content,
        color=style["color"],
        timestamp=None
    )
    
    if title:
        embed.title = title
    
    final_author_name = custom_author_name or style["author_text"]
    
    if final_author_name or style["author_icon_url"]:
        embed.set_author(name=final_author_name or "", icon_url=style["author_icon_url"] if style["author_icon_url"] else None)
    
    if use_thumb:
        if image_url:
             embed.set_thumbnail(url=image_url)
        elif style["thumbnail_url"]:
            embed.set_thumbnail(url=style["thumbnail_url"])
    elif image_url:
        embed.set_image(url=image_url)
    
    embed.set_footer(text=style["footer_text"], icon_url=style["footer_icon_url"] if style["footer_icon_url"] else None)

    await client.followup(interaction, embeds=[embed], ephemeral=is_ephemeral)
