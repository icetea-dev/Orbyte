import webview
import logging
import os
import json
import base64
import sqlite3
from datetime import datetime, timedelta

class WebAPI:
    def __init__(self, ui_instance):
        self._ui = ui_instance
        self.logger = logging.getLogger(__name__)

    def get_activity_history(self, days=7):
        """
        Get activity counts grouped by day for the last N days.
        Returns: {
            'labels': ['YYYY-MM-DD', ...],
            'messages': [count, ...],
            'reactions': [count, ...],
            'pings': [count, ...],
            'servers': [count, ...]
        }
        """
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, "activity.db")
            if not os.path.exists(db_path):
                return {'success': False, 'error': 'Database not found'}

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Generate all dates in range to ensure 0-filling
            date_list = []
            curr = start_date
            while curr <= end_date:
                date_list.append(curr.strftime('%Y-%m-%d'))
                curr += timedelta(days=1)
            
            conn = sqlite3.connect(db_path, timeout=10.0)
            c = conn.cursor()
            
            # Helper to get counts per day for a specific type
            def get_counts(activity_type):
                c.execute('''
                    SELECT date(timestamp), count(*)
                    FROM activity_log
                    WHERE type=? AND timestamp >= ?
                    GROUP BY date(timestamp)
                ''', (activity_type, start_date.strftime('%Y-%m-%d')))
                return dict(c.fetchall())

            msg_counts = get_counts('message_sent')
            react_counts = get_counts('reaction_added')
            ping_counts = get_counts('ping_received')
            server_counts = get_counts('server_join')
            
            conn.close()

            # Align data with date_list
            data = {
                'labels': date_list,
                'messages': [msg_counts.get(d, 0) for d in date_list],
                'reactions': [react_counts.get(d, 0) for d in date_list],
                'pings': [ping_counts.get(d, 0) for d in date_list],
                'servers': [server_counts.get(d, 0) for d in date_list]
            }
            return {'success': True, 'data': data}
            
        except Exception as e:
            self.logger.error(f"Error fetching activity history: {e}")
            return {'success': False, 'error': str(e)}

    def save_controller_token(self, token):
        """Save the Controller Bot Token to config."""
        try:
            self._ui._config_manager.config['discord']['controller_token'] = token
            self._ui._config_manager.save_config()
            return {'success': True}
        except Exception as e:
            self.logger.error(f"Failed to save controller token: {e}")
            return {'success': False, 'error': str(e)}

    def open_url(self, url):
        """Open a URL in the default system browser."""
        import subprocess
        import platform
        import webbrowser
        
        try:
            if platform.system() == 'Windows':
                subprocess.Popen(f'start "" "{url}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                webbrowser.open(url)
            return {'success': True}
        except Exception as e:
            self.logger.error(f"Failed to open URL: {e}")
            return {'success': False, 'error': str(e)}

    def setup_and_login(self, user_token, controller_token):
        """Save both tokens and start the bot."""
        try:
            self.logger.info("🔧 Running initial setup with both tokens...")
            # Save configs first
            self._ui._config_manager.set('discord.token', user_token)
            if controller_token:
                self._ui._config_manager.set('discord.controller_token', controller_token)
            else:
                # If explicit skip/empty, ensure it is clear? Or kept if existing?
                # Assuming overwrite if passed as argument
                pass 

            # Start bot
            return self._ui._bot_worker.validate_and_start(user_token)
        except Exception as e:
            self.logger.error(f"Setup failed: {e}")
            return {'success': False, 'error': str(e)}

    def rename_script(self, old_path, new_path):
        """Rename a script file from old_path to new_path. Returns True on success."""
        try:
            # Debug log for start of rename operation
            self.logger.debug(f"[DEBUG] Starting rename operation - From: {old_path}, To: {new_path}")
            
            # Verify that the old file exists
            if not os.path.exists(old_path):
                self.logger.error(f"[DEBUG] Rename failed - Old file does not exist: {old_path}")
                return False
                
            # Verify it is a Python file
            if not old_path.endswith('.py'):
                self.logger.error(f"[DEBUG] Rename failed - Not a Python script: {old_path}")
                return False
            
            # Rename the file
            os.rename(old_path, new_path)
            self.logger.info(f"[DEBUG] Script successfully renamed: {old_path} -> {new_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"[DEBUG] Error during script rename: {e}")
            return False
            
    def load_script(self, path):
        """Load and return the content of a script file for the frontend."""
        try:
            # Debug log for start of load operation
            self.logger.debug(f"[DEBUG] Starting script load operation - Path: {path}")
            
            if os.path.exists(path) and path.endswith('.py'):
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.logger.debug(f"[DEBUG] Script loaded successfully: {path} ({len(content)} characters)")
                    return content
            else:
                self.logger.debug(f"[DEBUG] Script load failed - File does not exist or not a Python script: {path}")
                return ''
        except Exception as e:
            self.logger.error(f"[DEBUG] Error during script load: {e}")
            return ''

    def delete_script(self, path):
        """Deletes a .py script from the scripts folder."""
        try:
            # Debug log for start of delete operation
            self.logger.debug(f"[DEBUG] Starting script delete operation - Path: {path}")
            
            if os.path.exists(path) and path.endswith('.py'):
                os.remove(path)
                self.logger.info(f"[DEBUG] Script successfully deleted: {path}")
                return True
            else:
                self.logger.debug(f"[DEBUG] Script delete failed - File does not exist or not a Python script: {path}")
                return False
        except Exception as e:
            self.logger.error(f"[DEBUG] Error during script delete: {e}")
            return False

    def reveal_in_explorer(self, path):
        """Opens file explorer at the script location."""
        import subprocess, platform
        file_path = os.path.abspath(path)
        try:
            if platform.system() == 'Windows':
                subprocess.Popen(f'explorer /select,"{file_path}"')
            elif platform.system() == 'Darwin':
                subprocess.Popen(['open', '-R', file_path])
            else:
                subprocess.Popen(['xdg-open', os.path.dirname(file_path)])
            self.logger.info(f"Reveal in explorer: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error reveal_in_explorer: {e}")
            return False

    def list_scripts(self):
        """Lists all .py scripts in the scripts/ folder for the frontend."""
        scripts_dir = 'scripts'
        
        # Create directory if it doesn't exist
        if not os.path.exists(scripts_dir):
            os.makedirs(scripts_dir)
        
        # Debug log for start of refresh operation
        self.logger.debug(f"[DEBUG] Starting scripts list refresh from directory: {scripts_dir}")
        
        scripts = []
        script_count = 0
        
        for file in os.listdir(scripts_dir):
            if file.endswith('.py'):
                script_count += 1
                file_path = os.path.join(scripts_dir, file).replace('\\', '/')
                scripts.append({
                    'name': file,
                    'path': file_path
                })
                self.logger.debug(f"[DEBUG] Found script: {file} at {file_path}")
        
        # Debug log for end of refresh operation
        self.logger.debug(f"[DEBUG] Scripts list refresh completed - Found {script_count} scripts")
        
        return scripts

    def save_script(self, path, content):
        """Save a script file to disk (called from JS)."""
        try:
            scripts_dir = 'scripts'
            
            # Create directory if it doesn't exist
            if not os.path.exists(scripts_dir):
                os.makedirs(scripts_dir)
            
            # Extract just the filename from full path
            filename = os.path.basename(path)
            file_path = os.path.join(scripts_dir, filename)
            
            # Debug log for script creation
            is_new_file = not os.path.exists(file_path)
            self.logger.debug(f"[DEBUG] Script save operation - Path: {file_path}, Is new file: {is_new_file}")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            if is_new_file:
                self.logger.info(f"[DEBUG] New script created: {file_path}")
            else:
                self.logger.info(f"[DEBUG] Existing script updated: {file_path}")
                
            return True
        except Exception as e:
            self.logger.error(f"Error during script save: {e}")
            return False
    
    def save_config(self, changes: dict):
        """Updates config with received values (key: path, value: new_value)"""
        try:
            ok = True
            for key, value in changes.items():
                if not self._ui._config_manager.set(key, value):
                    ok = False
            return {"success": ok}
        except Exception as e:
            self.logger.error(f"Error during config save: {e}")
            return {"success": False, "error": str(e)}

    def get_config(self):
        """Exposes full configuration to JS frontend"""
        return self._ui._config_manager.config

    def try_initial_login(self):
        self.logger.info("Frontend requested initial login attempt.")
        token = self._ui._config_manager.get_token()
        if not token:
            return {'success': False, 'error': 'No token configured.'}
        return self._ui._bot_worker.validate_and_start(token)

    def login_with_new_token(self, token):
        self.logger.info("Frontend attempting login with a new token.")
        if not token or not isinstance(token, str):
            return {'success': False, 'error': 'Token is missing or invalid.'}
        return self._ui._bot_worker.validate_and_start(token)

    def get_local_image(self, path):
        """Read a local image file and return it as a Base64 data URI."""
        try:
            if not os.path.exists(path):
                return {'success': False, 'error': 'File not found'}
            
            # Basic check to ensure it's a file
            if not os.path.isfile(path):
                return {'success': False, 'error': 'Not a file'}

            with open(path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Determine mime type based on extension
            ext = os.path.splitext(path)[1].lower()
            mime_type = "image/png" # default
            if ext in ['.jpg', '.jpeg']:
                mime_type = "image/jpeg"
            elif ext == '.gif':
                mime_type = "image/gif"
            elif ext == '.webp':
                mime_type = "image/webp"
            elif ext == '.svg':
                mime_type = "image/svg+xml"
                
            return {
                'success': True, 
                'data': f"data:{mime_type};base64,{encoded_string}"
            }
        except Exception as e:
            self.logger.error(f"Error reading local image: {e}")
            return {'success': False, 'error': str(e)}

    def set_activity(self, data):
        """Update Discord Rich Presence."""
        try:
            return self._ui._bot_worker.set_presence(data)
        except Exception as e:
            self.logger.error(f"Error setting activity: {e}")
            return {'success': False, 'error': str(e)}

    def clear_activity(self):
        """Clear Discord Rich Presence."""
        try:
            return self._ui._bot_worker.clear_presence()
        except Exception as e:
            self.logger.error(f"Error clearing activity: {e}")
            return {'success': False, 'error': str(e)}

            self.logger.error(f"Error clearing activity: {e}")
            return {'success': False, 'error': str(e)}

    def get_current_user_info(self):
        """Get current bot user info."""
        try:
            return self._ui._bot_worker.get_self_info()
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_controller_info(self):
        """Get controller bot info."""
        try:
            return self._ui._bot_worker.get_controller_info()
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def upload_rpc_image(self, base64_data):
        """Upload base64 image to Discord and get URL."""
        try:
            if not self._bot_worker:
                return {'success': False, 'error': 'Bot not initialized'}
            # Remove header if present
            if ',' in base64_data:
                header, encoded = base64_data.split(',', 1)
            else:
                encoded = base64_data
            
            data = base64.b64decode(encoded)
            return self._ui._bot_worker.upload_image_to_discord(data)
        except Exception as e:
            self.logger.error(f"Error uploading RPC image: {e}")
            return {'success': False, 'error': str(e)}

    def run_script_content(self, filename, content):
        """Called from JS to execute script content."""
        import asyncio # Import asyncio here if not already imported globally
        if not self._ui._bot_worker.loop: # Changed from self._bot_worker to self._ui._bot_worker
            return {'success': False, 'error': "Bot loop NOT active"}
        
        asyncio.run_coroutine_threadsafe(
            self._ui._bot_worker.run_script(content, filename), # Changed from self._bot_worker to self._ui._bot_worker
            self._ui._bot_worker.loop # Changed from self._bot_worker to self._ui._bot_worker
        )
        # We don't wait for result here because it runs async and sends events back
        # But we could return success=True to indicate it started.
        return {'success': True}

    def stop_script_content(self, filename):
        """Called from JS to stop the running script."""
        import asyncio # Import asyncio here if not already imported globally
        if not self._ui._bot_worker.loop:
             return {'success': False, 'error': "Bot loop NOT active"}
        
        asyncio.run_coroutine_threadsafe(
            self._ui._bot_worker.stop_script(filename),
            self._ui._bot_worker.loop
        )
        return {'success': True}
            
class UIWeb:
    def __init__(self, config_manager, bot_worker):
        self._config_manager = config_manager
        self._bot_worker = bot_worker
        self.window = None
        self.api = WebAPI(self)
        self.logger = logging.getLogger(__name__)
        self._bot_worker.ui_callback = self.handle_bot_callback

    def get_html_path(self):
        return os.path.join(os.path.dirname(__file__), 'interface', 'index.html')

    def handle_bot_callback(self, event_type, data):
        """
        Forwards events from the bot_worker to the frontend.
        Uses window.handlePythonEvent(...) when available (that's what your app.js exposes).
        """
        if not self.window:
            # window not available yet, log and skip (should be rare)
            self.logger.debug("UI window not ready to receive event.")
            return

        js_data = json.dumps(data)
        # JS safety: try window.handlePythonEvent first, fallback to dispatchEvent
        js_code = (
            "try {"
            f" if (window.handlePythonEvent) {{ window.handlePythonEvent({json.dumps(event_type)}, {js_data}); }}"
            " else { window.dispatchEvent(new CustomEvent('pythonEvent', { detail: { type: " +
            json.dumps(event_type) + ", data: " + js_data + " } })); }"
            "} catch (e) { console.error('Error delivering python event to UI', e); }"
        )
        try:
            self.window.evaluate_js(js_code)
        except Exception:
            # evaluate_js can fail if the page is reloading - log and ignore
            self.logger.exception("Failed to evaluate JS for handle_bot_callback")


    def start(self):
        self.logger.info("[DEBUG] Calling UIWeb.start(): creating webview window...")
        self.window = webview.create_window(
            "Orbyte - Selfbot",
            url=self.get_html_path(),
            width=1200, height=800,
            resizable=False,
            js_api=self.api,
            background_color='#030409',
            text_select=False  # Allow text selection
        )
        webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = True
        webview.start(debug=False, private_mode=True)

    def run(self):
        self.start()

def create_ui(config_manager, bot_worker):
    return UIWeb(config_manager, bot_worker)
