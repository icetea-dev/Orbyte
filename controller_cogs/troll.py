from controller_commands import CommandGroup, Option

# Troll Command Group definition
troll = CommandGroup("troll", "Fun and trolling commands")

@troll.command("spam", "Spam a message", options=[
    Option("text", "Text to spam", Option.STRING),
    Option("count", "How many times", Option.INTEGER)
])
async def troll_spam(client, interaction):
    from controller_commands import get_arg
    
    await client.send_response(interaction, "😈 Starting spam...", ephemeral=True)
    text = get_arg(interaction, "text")
    count = get_arg(interaction, "count") or 5
    
    channel_id = interaction.get('channel_id')
    channel = client.selfbot.get_channel(int(channel_id))
    if channel:
        import asyncio
        for _ in range(count):
            await channel.send(text)
            await asyncio.sleep(1.5)

@troll.command("ghostping", "Ghostping a user", options=[
    Option("user", "User to ghostping", Option.USER)
])
async def troll_ghostping(client, interaction):
    from controller_commands import get_arg
    
    await client.send_response(interaction, "😈 Ghostpinging...", ephemeral=True)
    user_id = get_arg(interaction, "user")
    
    channel_id = interaction.get('channel_id')
    channel = client.selfbot.get_channel(int(channel_id))
    if channel:
        message = await channel.send(f'<@!{user_id}>')
        await message.delete()
        