import os
import sys
import json
import time
import requests
import subprocess
from pathlib import Path

# Constants
MANIFEST_URL = "{REPO_URL}/manifest.json" # Will be replaced by main.py or hardcoded
RAW_BASE_URL = "{REPO_URL}" # Base URL for raw content

def download_file(url, target_path):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            # Ensure we write with utf-8 to avoid encoding issues
            with open(target_path, 'wb') as f:
                f.write(r.content)
            return True
        else:
            print(f"❌ Failed to download {url} (Status: {r.status_code})")
            return False
    except Exception as e:
        print(f"❌ Error downloading {url}: {e}")
        return False

def main():
    print("========================================")
    print("       ORBYTE AUTO-UPDATER")
    print("========================================")
    
    # parse args if needed, or just assume runtime config
    # We expect REPO_URL to be passed or hardcoded. 
    # For now, let's assume the caller (main.py) passes the base raw url as arg 1
    
    if len(sys.argv) < 2:
        print("❌ Error: Repository URL not provided.")
        time.sleep(3)
        sys.exit(1)
        
    repo_raw_url = sys.argv[1]
    
    print("⏳ Waiting for application to close...")
    time.sleep(2) # Give main.py time to exit
    
    print(f"🌐 Connecting to {repo_raw_url}...")
    
    # 1. Fetch Manifest
    manifest_url = f"{repo_raw_url}/manifest.json"
    print(f"📄 Fetching manifest: {manifest_url}")
    
    try:
        r = requests.get(manifest_url, timeout=10)
        if r.status_code != 200:
            print(f"❌ Failed to fetch manifest. Status: {r.status_code}")
            time.sleep(5)
            sys.exit(1)
        
        files_to_update = r.json()
    except Exception as e:
        print(f"❌ Failed to parse manifest: {e}")
        time.sleep(5)
        sys.exit(1)
        
    print(f"📦 Found {len(files_to_update)} files to update.")
    
    # 2. Update Files
    success_count = 0
    fail_count = 0
    
    for relative_path in files_to_update:
        print(f"⬇️ Updating: {relative_path}...")
        
        # Build URL and Local Path
        file_url = f"{repo_raw_url}/{relative_path}"
        local_path = Path(os.getcwd()) / relative_path
        
        if download_file(file_url, local_path):
            success_count += 1
        else:
            fail_count += 1
            
    print("-" * 40)
    print(f"✅ Update complete: {success_count} updated, {fail_count} failed.")
    
    if fail_count > 0:
        print("⚠️ Some files failed to update. Please check your connection.")
        time.sleep(5)
    else:
        print("🚀 Relaunching application...")
        time.sleep(1)
        
    # 3. Relaunch
    if os.path.exists("main.py"):
        subprocess.Popen([sys.executable, "main.py"])
    else:
        print("❌ Could not find main.py to relaunch!")
        time.sleep(5)

if __name__ == "__main__":
    main()
