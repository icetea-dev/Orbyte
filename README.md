# Discord Selfbot & Controller System

A comprehensive dual-instance Discord bot specifically designed for power users. This project integrates a **Selfbot** for user account automation and a **Controller Bot** for external command handling, managed via a unified dashboard.

> **⚠️ DISCLAIMER**  
> Automating user accounts ("Selfbotting") is against Discord's Terms of Service. This software is for **educational purposes only**. The developers are not responsible for any account bans or suspensions resulting from the use of this tool. Use at your own risk.

## 🚀 Key Features

### 🤖 Dual-Core Architecture
- **Selfbot Instance**: Handles user-specific actions, activity logging, and automation tasks.
- **Controller Bot**: A lightweight bot instance for executing slash commands and managing the selfbot externally without flagging anti-spam systems.

### 💻 Integrated Dashboard
- **Scripting Engine**: Write, save, and run custom Python scripts directly from the UI.
- **Rich Presence (RPC) Editor**: Customize your Discord status with custom assets, buttons, and timestamps.
- **Activity Logger**: Track joins, leaves, pings, and friend requests locally.

### 🛠️ Advanced Tools
- **Nitro Sniper**: Optimized gift code claimer (configurable).
- **Platform Spoofer**: Mask your client connection (Mobile, Web, Desktop).
- **Code Editor**: Monaco-based editor for on-the-fly script modifications.

## 📋 Prerequisites
- Python 3.8+
- A Discord User Token (for the Selfbot)
- A Discord Bot Token (for the Controller)

## ⚙️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/icetea-dev/Orbyte.git
   cd Orbyte
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configuration**
   The application handles configuration via the UI, but you can manually configure `config.json` after the first launch.

##  ▶️ Usage

Run the main application entry point:
```bash
python main.py
```
This will launch the Webview window and start the backend worker processes.

## 🔄 Auto-Update System
The application automatically checks for updates on startup.
- If a new version is detected, it closes the app and launches `updater.py`.
- **Warning**: The updater **overwrites core files** listed in `manifest.json`.
- **Do NOT modify core files** (e.g., `bot_worker.py`) directly, or your changes will be lost.
- Use `scripts/` or create new files in `controller_cogs/` to add custom functionality safely.


## 📝 Scripting API
The built-in scripting engine provides a powerful environment for customizing the bot. 
 **Exposed Variables:**
- `bot`: The selfbot instance (wrapper).
- `discord`: The `discord.py-self` library.
- `asyncio`: The `asyncio` library.
- `commands`: The `discord.ext.commands` module.
- `ctx`: Context (available depending on scope).
- `print`: Redirected to the real-time script console.

**Checking Custom Libraries:**
You can import any standard Python library (e.g., `import math`, `import random`) or installed package directly in your script.

Example:
```python
# Simple auto-reply script
@bot.event
async def on_message(message):
    if message.content == "ping":
        await message.channel.send("pong")

# Custom Command Example
@bot.command()
async def hello(ctx):
    await ctx.send("Hello from the Selfbot Scripting Engine!")
```


## 🗺️ Roadmap

### 🚀 Potential Improvements
- [ ] **Themes**: Add accent color picker for the dashboard.
- [ ] **More Commands**: Add more commands to the controller bot.

## 🤝 Contributing
Contributions are welcome! Please ensure that your code is clean and documented.

## 📄 License
[GNU General Public License v3.0](LICENSE)
