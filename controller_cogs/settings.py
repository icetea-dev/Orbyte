from controller_commands import CommandGroup, Option

# Settings Command Group definition
settings = CommandGroup("settings", "Manage bot settings")

@settings.command("forwarding", "Enable or disable auto-forwarding of embeds by Selfbot", options=[
    Option("enabled", "Enable forwarding? (True = Selfbot sends, False = Controller shows)", Option.BOOLEAN, required=True)
])
async def settings_forwarding(client, interaction):
    """
    Handler for /settings forwarding.
    Toggles whether embeds are sent by the Selfbot (Public) or Controller (Private).
    """
    from controller_commands import get_arg
    
    new_state = get_arg(interaction, "enabled")
    client.config_manager.set("discord.controller_forwarding", new_state)
    
    state_str = "📤 Forwarding ON (Selfbot posts publicly)" if new_state else "🤖 Forwarding OFF (Controller shows embed)"
    
    await client.send_response(
        interaction, 
        f"✅ Configuration updated!\nMode: **{state_str}**", 
        ephemeral=True
    )

@settings.command("ephemeral", "Set if bot responses are private (ephemeral) or public", options=[
    Option("enabled", "Enable private responses?", Option.BOOLEAN, required=True)
])
async def settings_ephemeral(client, interaction):
    """
    Handler for /settings ephemeral.
    Toggles whether Controller command responses are visible only to the user.
    """
    from controller_commands import get_arg
    
    new_state = get_arg(interaction, "enabled")
    
    client.config_manager.set("discord.controller_ephemeral", new_state)
    
    state_str = "🔒 Private (Only you see them)" if new_state else "📢 Public (Everyone sees them)"
    
    await client.send_response(
        interaction, 
        f"✅ Configuration updated!\nBot responses are now: **{state_str}**", 
        ephemeral=True
    )

@settings.command("nitro_sniper", "Enable or disable the Nitro Sniper", options=[
    Option("enabled", "Enable Nitro Sniper?", Option.BOOLEAN, required=True)
])
async def settings_nitro_sniper(client, interaction):
    """
    Handler for /settings nitro_sniper.
    Enables or disables the automatic Nitro gift code claimer.
    """
    from controller_commands import get_arg
    new_state = get_arg(interaction, "enabled")
    client.config_manager.set("nitro_sniper", new_state)
    
    state_str = "🚀 Sniper ON" if new_state else "🛑 Sniper OFF"
    await client.send_response(
        interaction,
        f"✅ Configuration updated!\nMode: **{state_str}**",
        ephemeral=True
    )

@settings.command("webhook", "Configure webhooks for events", options=[
    Option("event", "Event type", Option.STRING, required=True, choices=[
        {"name": "Pings", "value": "pings"},
        {"name": "Ghost Pings", "value": "ghostpings"},
        {"name": "Nitro Snipes", "value": "nitro_snipes"},
        {"name": "New Roles", "value": "new_roles"},
        {"name": "Unfriended", "value": "unfriended"}
    ]),
    Option("url", "Webhook URL (Leave empty to keep current)", Option.STRING, required=False),
    Option("enabled", "Enable or disable this event?", Option.BOOLEAN, required=False)
])
async def settings_webhook(client, interaction):
    """
    Handler for /settings webhook.
    Configures webhook settings for specific events.
    """
    from controller_commands import get_arg
    
    event = get_arg(interaction, "event").lower()
    url = get_arg(interaction, "url")
    enabled = get_arg(interaction, "enabled")
    
    valid_events = ["pings", "ghostpings", "nitro_snipes", "new_roles", "unfriended"]
    
    if event not in valid_events:
        await client.send_response(
            interaction,
            f"❌ Invalid event type. Valid events: {', '.join(valid_events)}",
            ephemeral=True
        )
        return

    config_path = f"webhooks.events.{event}"
    current_config = client.config_manager.get(config_path)
    
    if not current_config:
        current_config = {"enabled": False, "webhook_url": ""}
    
    changes = []
    
    if url is not None:
        if url.strip() and not url.startswith("http"):
             await client.send_response(interaction, "❌ Invalid URL format.", ephemeral=True)
             return
        
        target_url = url.strip()
        client.config_manager.set(f"{config_path}.webhook_url", target_url)
        changes.append(f"URL: `{target_url[:20]}...`" if target_url else "URL: `Cleared`")
        
    if enabled is not None:
        client.config_manager.set(f"{config_path}.enabled", enabled)
        changes.append(f"Status: **{'ON' if enabled else 'OFF'}**")
    
    if not changes:
         await client.send_response(interaction, "ℹ️ No changes were made.", ephemeral=True)
         return

    await client.send_response(
        interaction,
        f"✅ **Webhook Config Updated** (`{event}`)\n" + "\n".join(changes),
        ephemeral=True
    )

