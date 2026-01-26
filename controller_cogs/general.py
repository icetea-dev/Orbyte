from controller_commands import CommandGroup, Option, controller_command, send_smart_embed, get_arg, get_embed_style
import discord

@controller_command(
    name="ping", 
    description="Check if the controller is alive"
)
async def ping_command(client, interaction):
    """
    Handler for /ping.
    Checks the latency of both the Selfbot and the Controller.
    """
    await client.defer(interaction)
    
    user_latency = "Unknown"
    if client.selfbot and hasattr(client.selfbot, 'latency'):
        user_latency = f"{round(client.selfbot.latency * 1000)}ms"
        
    app_latency = "Unknown"
    if hasattr(client, 'latency') and client.latency != float('inf'):
        app_latency = f"{round(client.latency * 1000)}ms"
    
    style = get_embed_style(client)
    
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"**App Latency**: `{app_latency}`\n**User Latency**: `{user_latency}`",
        color=style["color"]
    )
    
    if style["author_icon_url"]:
        embed.set_author(name=style["author_text"], icon_url=style["author_icon_url"])
    else:
        embed.set_author(name=style["author_text"])
        
    if style["thumbnail_url"]:
        embed.set_thumbnail(url=style["thumbnail_url"])
        
    embed.set_footer(text=style["footer_text"], icon_url=style["footer_icon_url"] if style["footer_icon_url"] else None)

    await send_smart_embed(client, interaction, embed)

lookup = CommandGroup("lookup", "Lookup commands")

@lookup.command("ip", "Lookup IP information", options=[
    Option("ip", "IP address to lookup", Option.STRING, required=True)
])
async def lookup_ip(client, interaction):
    """
    Handler for /lookup ip.
    Retrieves information about an IP address using ip-api.com.
    """
    await client.defer(interaction)
    ip = get_arg(interaction, "ip")

    try:
        async with client.session.get(f"http://ip-api.com/json/{ip}?fields=61439") as response:
            if response.status == 200:
                data = await response.json()
                
                if data.get("status") == "fail":
                    await client.followup(interaction, f"❌ API Error: {data.get('message', 'Unknown error')}")
                    return

                lines = [
                    f"**IP**: {data.get('query', ip)}",
                    f"**City**: {data.get('city', 'Unknown')}",
                    f"**Region**: {data.get('regionName', 'Unknown')}",
                    f"**Country**: {data.get('country', 'Unknown')}",
                    f"**Timezone**: {data.get('timezone', 'Unknown')}",
                    f"**ISP**: {data.get('isp', 'Unknown')}",
                ]

                content = "\n".join(lines)

                style = get_embed_style(client)
                author_text = style["author_text"]
                author_icon = style["author_icon_url"]
                thumbnail_url = style["thumbnail_url"]
                footer_text = style["footer_text"]
                footer_icon = style["footer_icon_url"]
                color = style["color"]

                embed = discord.Embed(
                    title=author_text,
                    description=content,
                    color=color,
                    timestamp=None
                )
            
                if author_icon:
                    embed.set_author(name="IP Lookup", icon_url=author_icon)
                else:
                    embed.set_author(name="IP Lookup")
                    
                if thumbnail_url:
                    embed.set_thumbnail(url=thumbnail_url)
                    
                embed.set_footer(text=footer_text, icon_url=footer_icon if footer_icon else None)

                await send_smart_embed(client, interaction, embed)

            else:
                text = await response.text()
                await client.followup(interaction, f"❌ Could not lookup IP {ip} (Status: {response.status})")
                
    except Exception as e:
        await client.followup(interaction, f"❌ An error occurred: {e}")