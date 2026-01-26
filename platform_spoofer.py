import sys
import json
import base64
import requests
import datetime
import os
import logging
from discord import utils

# Logger for this module
log = logging.getLogger(__name__)

class PlatformSpoofer:
    """
    Handles platform spoofing by monkey-patching discord.utils.Headers.default
    to inject custom super_properties.
    """
    
    CACHE_FILE = "build_number_cache.json"
    
    PROPERTIES_TEMPLATES = {
        "desktop": {
            "os": "Windows",
            "browser": "Discord Client",
            "device": "",
            "system_locale": "en-US",
            "browser_user_agent": "",
            "release_channel": "stable",
            "client_build_number": None,
            "client_event_source": None
        },
        "web": {
            "os": "Windows",
            "browser": "Discord Web",
            "device": "",
            "system_locale": "en-US",
            "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "release_channel": "stable",
            "client_build_number": None,
            "client_event_source": None
        },
        "mobile": {
            "os": "iOS",
            "browser": "Discord iOS",
            "device": "iPhone14,5",
            "system_locale": "en-US",
            "browser_user_agent": "Discord/205.0 (iPhone; iOS 16.6; Scale/3.00)",
            "os_version": "16.6",
            "release_channel": "stable",
            "client_build_number": None,
            "client_event_source": None
        },
        "playstation": {
            "os": "PlayStation",
            "browser": "Discord Embedded",
            "device": "PlayStation 5",
            "system_locale": "en-US",
            "browser_user_agent": "Mozilla/5.0 (PlayStation; PlayStation 5/2.26) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0 Safari/605.1.15",
            "release_channel": "stable",
            "client_build_number": None,
            "client_event_source": None
        }
    }

    @staticmethod
    def get_latest_build_number():
        """
        Fetches the latest Discord build number with local caching (valid for 1 hour).
        """
        now_ts = datetime.datetime.now().timestamp()
        
        if os.path.exists(PlatformSpoofer.CACHE_FILE):
            try:
                with open(PlatformSpoofer.CACHE_FILE, "r") as f:
                    data = json.load(f)
                    if data.get("timestamp") and now_ts - data.get("timestamp") < 21600:
                        return data.get("build_number")
            except Exception as e:
                log.warning(f"Failed to load build number cache: {e}")

        try:
            pass 

            r = requests.get("https://discord.com/login", timeout=5)
            if r.status_code == 200:
                import re
                asset_match = re.search(r'assets/([a-f0-9]+)\.js', r.text)
                if asset_match:
                    asset_id = asset_match.group(1)
                    r2 = requests.get(f"https://discord.com/assets/{asset_id}.js", timeout=5)
                    if r2.status_code == 200:
                        build_match = re.search(r'Build Number: \"(\d+)\"', r2.text)
                        if not build_match: # Try alternative format
                            build_match = re.search(r'build_number:\"(\d+)\"', r2.text)
                            
                        if build_match:
                            build_num = int(build_match.group(1))
                            # Save to cache
                            with open(PlatformSpoofer.CACHE_FILE, "w") as f:
                                json.dump({"build_number": build_num, "timestamp": now_ts}, f)
                            log.info(f"Fetched latest Discord Build Number: {build_num}")
                            return build_num
                            
        except Exception as e:
            log.warning(f"Failed to fetch live build number, using fallback: {e}")

        return 350000 

    @classmethod
    def patch(cls, platform_key="desktop"):
        """
        Monkey-patches discord.utils.Headers.default to return custom properties.
        """
        target_props = cls.PROPERTIES_TEMPLATES.get(platform_key, cls.PROPERTIES_TEMPLATES["desktop"])
        
        build_num = cls.get_latest_build_number()
        target_props["client_build_number"] = build_num

        log.info(f"Applying Platform Spoofing: {platform_key} (Build: {build_num})")
        json_props = json.dumps(target_props)
        encoded_props = base64.b64encode(json_props.encode()).decode("utf-8")

        async def custom_default(cls_ref, session, proxy=None, proxy_auth=None):
            return cls_ref(
                platform=target_props.get("os", "Windows"),
                major_version=100,
                super_properties=target_props,
                encoded_super_properties=encoded_props,
                extra_gateway_properties={} 
            )

        utils.Headers.default = classmethod(custom_default)
