import json
import os
import logging
from pathlib import Path

class ConfigManager:
    def __init__(self, config_file='config.json'):
        self.config_file = Path(config_file)
        self.default_config = {
            'discord': {
                'token': '',
                'controller_token': '',
                'command_prefix': ',',
                'controller_ephemeral': True,
                'controller_forwarding': False,
                "platform": "desktop"
            },
            "ui": {
                "background_file": ""
            },
            "nitro_sniper": {
                "enabled": False
            },
            "rpc": {
                "enabled": False,
                "name": "",
                "details": "",
                "state": "",
                "large_image": "",
                "large_text": "",
                "small_image": "",
                "small_text": "",
                "timestamp_mode": False,
                "timestamp_offset": 0,
                "button1_label": "",
                "button1_url": "",
                "button2_label": "",
                "button2_url": ""
            },
            "webhooks": {
                "events": {
                    "pings": { "enabled": False, "webhook_url": "" },
                    "ghostpings": { "enabled": False, "webhook_url": "" },
                    "nitro_snipes": { "enabled": False, "webhook_url": "" },
                    "new_roles": { "enabled": False, "webhook_url": "" },
                    "unfriended": { "enabled": False, "webhook_url": "" }
                }
            }
        }
        self.config = self.load_config()
        
    def load_config(self):
        """Load configuration from file or create default"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # Merge with default config to add any missing keys
                return self._merge_configs(self.default_config, config)
            else:
                # Create default config file
                self.save_config(self.default_config)
                return self.default_config.copy()
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            return self.default_config.copy()
    
    def save_config(self, config=None):
        """Save configuration to file"""
        try:
            config_to_save = config if config is not None else self.config
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"Error saving config: {e}")
            return False
    
    def get(self, key_path, default=None):
        """Get configuration value using dot notation (e.g., 'discord.token')"""
        try:
            keys = key_path.split('.')
            value = self.config
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key_path, value):
        """Set configuration value using dot notation"""
        try:
            keys = key_path.split('.')
            config = self.config
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]
            config[keys[-1]] = value
            return self.save_config()
        except Exception as e:
            logging.error(f"Error setting config value: {e}")
            return False
    
    def validate_token(self, token):
        """Validate Discord token format and length"""
        if not token or not isinstance(token, str):
            return False
        token = token.strip()
        if len(token) < 50:
            return False
        if token.count('.') < 2:
            return False
        return True
    
    def update_token(self, token):
        """Update Discord token with validation"""
        if self.validate_token(token):
            return self.set('discord.token', token)
        return False
    
    def get_token(self):
        """Get Discord token"""
        return self.get('discord.token', '')
    
    def reset_to_defaults(self):
        """Reset configuration to default values"""
        self.config = self.default_config.copy()
        return self.save_config()
    
    def _merge_configs(self, default, user):
        """Recursively merge user config with default config"""
        result = default.copy()
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result
    
    def export_config(self, file_path):
        """Export current configuration to a file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"Error exporting config: {e}")
            return False
    
    def import_config(self, file_path):
        """Import configuration from a file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)
            self.config = self._merge_configs(self.default_config, imported_config)
            return self.save_config()
        except Exception as e:
            logging.error(f"Error importing config: {e}")
            return False