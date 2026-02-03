from controller_commands import controller_command, Option, send_smart_embed, COMMANDS_REGISTRY, CommandGroup, get_embed_style, get_arg
import discord
import logging

# Define emojis for known categories
CATEGORY_EMOJIS = {
    "info": "ℹ️",
    "troll": "🤡",
    "settings": "🛠️",
    "lookup": "🔍",
    "general": "⚙️",
    "help": "❓",
    "embed": "📝",
    "nsfw": "🔞"
}

CATEGORY_DESCRIPTIONS = {
    "info": "Info related commands",
    "troll": "Fun and trolling commands",
    "settings": "Manage bot settings",
    "lookup": "Lookup commands",
    "general": "General purpose commands",
    "embed": "Embed creation commands",
    "nsfw": "NSFW commands"
}

async def help_autocomplete(client, interaction):
    choices = []
    # Suggest categories
    for key, value in COMMANDS_REGISTRY.items():
        if isinstance(value, CommandGroup):
            emoji = CATEGORY_EMOJIS.get(key, '📁')
            choices.append({"name": f"{emoji} {key.capitalize()}", "value": key})
    
    # Also add "general" if there are top-level commands
    has_top_level = False
    for key, value in COMMANDS_REGISTRY.items():
        if isinstance(value, dict) and "data" in value and key != "help":
             has_top_level = True
             break
    
    if has_top_level:
         choices.append({"name": "⚙️ General", "value": "general"})

    # Filter by user input
    current_val = ""
    target_opt = None
    
    data = interaction.get('data', {})
    options = data.get('options', [])
    
    for opt in options:
        if opt.get('focused'):
            current_val = opt.get('value', "")
            break
            
    current_val = str(current_val).lower()
    
    filtered_choices = [c for c in choices if current_val in c['name'].lower() or current_val in c['value'].lower()]
    
    try:
        await client.send_autocomplete_result(interaction, filtered_choices[:25])
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to send help autocomplete: {e}")

@controller_command(
    name="help",
    description="Show all commands or details for a specific category",
    options=[
        Option("category", "The category to get help for", Option.STRING, required=False, autocomplete=True)
    ],
    autocomplete=help_autocomplete
)
async def help_command(client, interaction):
    """
    Handler for /help.
    """
    # Preliminary Checks
    if not client.selfbot or not client.selfbot.is_ready():
        pass

    # We defer purely for enough time to process
    pass
    
    await client.defer(interaction)
    
    query = get_arg(interaction, "category")
    style = get_embed_style(client)
    
    # Set default styling elements
    author_text = style["author_text"]
    author_icon = style["author_icon_url"]
    footer_text = style["footer_text"]
    footer_icon = style["footer_icon_url"]
    color = style["color"]
    thumb = style["thumbnail_url"]

    # === MODE 1: Overview (No Query) ===
    if not query:
        embed = discord.Embed(
             title=f"{CATEGORY_EMOJIS.get('help', '❓')} Help Menu",
             description=f"Welcome to **{author_text}**!\nHere are the available command categories.\nUse `/help <category>` to view commands in a specific category.",
             color=color
        )
        
        # Collect Categories
        categories = {}
        
        # 1. Command Groups
        for key, value in COMMANDS_REGISTRY.items():
             if isinstance(value, CommandGroup):
                 desc = value.description
                 categories[key] = desc
        
        # 2. General (Top-level commands)
        general_count = 0
        for key, value in COMMANDS_REGISTRY.items():
            if isinstance(value, dict) and "data" in value:
                if key != "help": # Exclude help itself from the count/list if desired, or keep it.
                    general_count += 1
        
        if general_count > 0:
             categories["general"] = "General purpose commands"
        
        # specific order if possible? Sort alphabetically
        sorted_cats = sorted(categories.keys())
        
        for cat in sorted_cats:
             desc = categories[cat]
             emoji = CATEGORY_EMOJIS.get(cat, '📁')
             
             embed.add_field(
                 name=f"{emoji} {cat.capitalize()}",
                 value=f"> `/help {cat}`\n> *{desc}*",
                 inline=True
             )
             
        if author_icon:
             embed.set_author(name=author_text, icon_url=author_icon)
        else:
             embed.set_author(name=author_text)
        
        embed.set_footer(text=footer_text, icon_url=footer_icon if footer_icon else None)
        if thumb:
            embed.set_thumbnail(url=thumb)
            
        await send_smart_embed(client, interaction, embed)
        return

    # === MODE 2: Category or Command Details ===
    query = query.lower()
    
    # Check if it is "general"
    if query == "general":
         lines = []
         for key, value in COMMANDS_REGISTRY.items():
             if isinstance(value, dict) and "data" in value and key != "help":
                 cmd_data = value["data"]
                 lines.append(f"**/{cmd_data['name']}**\n{cmd_data['description']}")
         
         if not lines:
             await client.followup(interaction, "❌ No general commands found.")
             return
             
         embed = discord.Embed(
             title=f"{CATEGORY_EMOJIS.get('general', '⚙️')} General Commands",
             description="\n\n".join(lines),
             color=color
         )
         
         if author_icon: embed.set_author(name=author_text, icon_url=author_icon)
         else: embed.set_author(name=author_text)
         if thumb: embed.set_thumbnail(url=thumb)
         embed.set_footer(text=footer_text, icon_url=footer_icon if footer_icon else None)
         
         await send_smart_embed(client, interaction, embed)
         return

    # Check if it is a specific Group
    if query in COMMANDS_REGISTRY and isinstance(COMMANDS_REGISTRY[query], CommandGroup):
        group = COMMANDS_REGISTRY[query]
        subcmds = group.subcommands
        
        lines = []
        for name, details in subcmds.items():
            desc = details['data']['description']
            lines.append(f"**/{query} {name}**\n{desc}")
        
        embed = discord.Embed(
             title=f"{CATEGORY_EMOJIS.get(query, '📁')} {query.capitalize()} Commands",
             description=f"Commands available in the **{query}** category.\n\n" + "\n\n".join(lines),
             color=color
        )
        
        if author_icon: embed.set_author(name=author_text, icon_url=author_icon)
        else: embed.set_author(name=author_text)
        if thumb: embed.set_thumbnail(url=thumb)
        embed.set_footer(text=footer_text, icon_url=footer_icon if footer_icon else None)
        
        await send_smart_embed(client, interaction, embed)
        return

    # Check if it is a top-level command
    if query in COMMANDS_REGISTRY and isinstance(COMMANDS_REGISTRY[query], dict):
        val = COMMANDS_REGISTRY[query]
        cmd_data = val["data"]
        
        embed = discord.Embed(
             title=f"Command: /{query}",
             description=cmd_data['description'],
             color=color
        )
        
        opts_list = []
        if cmd_data.get('options'):
            for o in cmd_data['options']:
                req = "Required" if o.get('required') else "Optional"
                opts_list.append(f"• **{o['name']}** ({req}): {o['description']}")
            
            embed.add_field(name="Options", value="\n".join(opts_list), inline=False)
            
        if author_icon: embed.set_author(name=author_text, icon_url=author_icon)
        else: embed.set_author(name=author_text)
        if thumb: embed.set_thumbnail(url=thumb)
        embed.set_footer(text=footer_text, icon_url=footer_icon if footer_icon else None)
        
        await send_smart_embed(client, interaction, embed)
        return
        
    await client.followup(interaction, f"❌ Category or command `{query}` not found.")
