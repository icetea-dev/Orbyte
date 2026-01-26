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
