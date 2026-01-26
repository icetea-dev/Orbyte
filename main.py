"""
Orbyte - Discord Selfbot Interface

A modern Discord selfbot with a sleek, futuristic UI.
"""

import sys
import os
import logging
import argparse
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    from config_manager import ConfigManager
    from bot_worker import BotWorker
    from ui_web import create_ui
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure all required files are in the same directory.")
    sys.exit(1)

APP_VERSION = "1.0.1"
REPO_RAW_URL = "https://raw.githubusercontent.com/icetea-dev/Orbyte/main"

class SelfbotApplication:
    """Main application class"""
    
    def __init__(self):
        self.config_manager = None
        self.bot_worker = None
        self.ui = None
        self.logger = None
        
    def setup_logging(self, debug=False):
        """Setup application logging"""
        log_level = logging.DEBUG if debug else logging.INFO
        
        logs_dir = Path('logs')
        logs_dir.mkdir(exist_ok=True)
        
        log_file = logs_dir / 'selfbot.log'
        if log_file.exists():
            log_file.unlink()
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, mode='w', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ],
            force=True
        )
        
        discord_logger = logging.getLogger('discord')
        discord_logger.setLevel(logging.WARNING)
        
        gateway_logger = logging.getLogger('discord.gateway')
        gateway_logger.setLevel(logging.ERROR)
        
        state_logger = logging.getLogger('discord.state')
        state_logger.setLevel(logging.ERROR)
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("Orbyte logging initialized")
    
    def initialize_components(self):
        """Initialize all application components"""
        try:
            # Initialize configuration manager
            if self.logger:
                self.logger.info("Initializing configuration manager...")
            self.config_manager = ConfigManager()
            
            # Initialize bot worker
            if self.logger:
                self.logger.info("Initializing bot worker...")
            self.bot_worker = BotWorker(self.config_manager)
            
            # Initialize UI
            if self.logger:
                self.logger.info("Initializing web UI...")
            self.ui = create_ui(self.config_manager, self.bot_worker)
            
            if self.logger:
                self.logger.info("All components initialized successfully")
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error initializing components: {e}")
            raise
    
    def check_dependencies(self):
        """Check if all required dependencies are available"""
        required_modules = [
            'discord',
            'webview',
            'asyncio',
            'json',
            'pathlib'
        ]
        
        missing_modules = []
        
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)
        
        if missing_modules:
            if self.logger:
                self.logger.error(f"Missing required modules: {missing_modules}")
                self.logger.error("Please install dependencies: pip install -r requirements.txt")
            return False
        
        return True
    
    def check_configuration(self):
        """Check if configuration is valid"""
        if not self.config_manager:
            return False
            
        token = self.config_manager.get_token()
        
        if not token:
            if self.logger:
                self.logger.warning("No Discord token configured")
                self.logger.info("You can configure the token through the web interface")
            return True  # Not critical, can be set later
        
        if not self.config_manager.validate_token(token):
            if self.logger:
                self.logger.warning("Invalid Discord token format")
                self.logger.info("Please check your token configuration")
            return True  # Not critical, can be fixed later
        
        if self.logger:
            self.logger.info("Configuration validated successfully")
        return True

    def check_for_updates(self):
        """Check for updates from the remote repository."""
        if self.logger:
            self.logger.info(f"Checking for updates (Current: v{APP_VERSION})...")
        
        try:
            # Need requests for this check
            import requests
            
            # Fetch remote version
            version_url = f"{REPO_RAW_URL}/version.txt"
            r = requests.get(version_url, timeout=3)
            
            if r.status_code == 200:
                remote_version = r.text.strip()
                if remote_version != APP_VERSION:
                    if self.logger:
                        self.logger.info(f"Update available! v{APP_VERSION} -> v{remote_version}")
                    
                    # Launch Updater
                    import subprocess
                    
                    updater_script = "updater.py"
                    if not os.path.exists(updater_script):
                        if self.logger: 
                            self.logger.error("updater.py not found. Cannot update locally.")
                        return

                    if self.logger:
                        self.logger.info("Launching updater and closing application...")
                    
                    creation_flags = 0
                    if sys.platform == "win32":
                        creation_flags = subprocess.CREATE_NEW_CONSOLE
                        
                    subprocess.Popen(
                        [sys.executable, updater_script, REPO_RAW_URL], 
                        creationflags=creation_flags
                    )
                    
                    sys.exit(0)
                else:
                    if self.logger:
                        self.logger.info("Application is up to date.")
            else:
                if self.logger:
                    self.logger.warning(f"Could not check for updates (Status: {r.status_code}). Skipping.")

        except SystemExit:
            raise
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Update check failed: {e}. Skipping.")
        return True

    def run(self):
        """Main application run method"""
        try:
            if self.logger:
                self.logger.info("=" * 50)
                self.logger.info("Orbyte - Selfbot Interface")
                self.logger.info("=" * 50)
            
            # Check dependencies
            if not self.check_dependencies():
                return False
            
            # Initialize components
            self.initialize_components()
            
            # Check configuration
            self.check_configuration()

            # Check for updates (Blocking check before UI start)
            self.check_for_updates()
            
            # Print startup information
            self.print_startup_info()
            
            # Start the UI (this will block until the window is closed)
            if self.logger:
                self.logger.info("Starting web interface...")
            if self.ui:
                self.ui.run()
            
            return True
            
        except KeyboardInterrupt:
            if self.logger:
                self.logger.info("Application interrupted by user")
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Fatal error: {e}")
            return False
        finally:
            self.cleanup()
    
    def print_startup_info(self):
        """Print startup information"""
        if not self.logger or not self.config_manager:
            return
            
        self.logger.info("Application ready!")
        self.logger.info(f"Configuration file: {self.config_manager.config_file}")
        
        token = self.config_manager.get_token()
        if token:
            self.logger.info("Discord token: Configured")
        else:
            self.logger.info("Discord token: Not configured")
            
        prefix = self.config_manager.get('discord.command_prefix', ',')
        self.logger.info(f"Command prefix: {prefix}")
        
        self.logger.info("-" * 60)
    
    def cleanup(self):
        """Cleanup resources"""
        if self.logger:
            self.logger.info("Cleaning up...")
        
        if self.bot_worker and self.bot_worker.is_running:
            self.logger.info("Bot is running, initiating shutdown...")
            self.bot_worker.shutdown()
        
        if self.logger:
            self.logger.info("Cleanup completed")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Discord Selfbot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Start with default settings
  python main.py --debug            # Start with debug logging
  python main.py --config custom.json  # Use custom config file
        """
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='config.json',
        help='Configuration file path (default: config.json)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Discord Selfbot v1.0.0'
    )
    
    return parser.parse_args()

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    return True

def main():
    """Main entry point"""
    if not check_python_version():
        sys.exit(1)
    
    args = parse_arguments()
    
    app = SelfbotApplication()
    
    app.setup_logging(debug=args.debug)
    
    if hasattr(app, 'config_manager') and app.config_manager:
        app.config_manager.config_file = Path(args.config)
    
    success = app.run()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()