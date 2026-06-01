#!/usr/bin/env python3
"""
Sync local contacts.json to Cloudflare Worker D1 Database.
Usage: python sync_contacts.py
"""
import json
import os
import sys
import urllib.request
import urllib.error
from dotenv import load_dotenv

# Fix Windows console encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

def sync_contacts():
    api_base_url = os.getenv("API_BASE_URL", "").rstrip("/")
    api_key = os.getenv("API_KEY", "")

    if not api_base_url or not api_key:
        print("[Sync] Error: API_BASE_URL or API_KEY not set in .env")
        return False

    # Load local contacts
    contacts_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contacts.json")
    if not os.path.exists(contacts_file):
        print(f"[Sync] Error: {contacts_file} not found")
        return False

    with open(contacts_file, "r", encoding="utf-8") as f:
        contacts = json.load(f)

    print(f"[Sync] Loaded {len(contacts)} contacts from {contacts_file}")

    # Build URL - Worker supports both /api and /api.php
    url = f"{api_base_url}/api?action=save_contacts"
    print(f"[Sync] Pushing to {url}...")

    try:
        payload = json.dumps(contacts).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "TikTok-Streak-Sync/1.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            status = res_data.get("status", "unknown")
            message = res_data.get("message", "")
            print(f"[Sync] Response status: {status}")
            print(f"[Sync] Message: {message}")
            if status == "success":
                print("[Sync] OK - Successfully synced contacts to D1 Database!")
                return True
            else:
                print(f"[Sync] FAIL - API returned error")
                return False
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[Sync] FAIL - HTTP Error {e.code}: {body}")
        return False
    except Exception as e:
        print(f"[Sync] FAIL - Error: {e}")
        return False


def verify_contacts():
    """Verify contacts were saved correctly by fetching them back."""
    api_base_url = os.getenv("API_BASE_URL", "").rstrip("/")
    api_key = os.getenv("API_KEY", "")

    url = f"{api_base_url}/api?action=get_contacts"
    print(f"\n[Verify] Fetching contacts from {url}...")

    try:
        req = urllib.request.Request(
            url,
            headers={
                "x-api-key": api_key,
                "Accept": "application/json",
                "User-Agent": "TikTok-Streak-Sync/1.0"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            if isinstance(data, list):
                print(f"[Verify] OK - D1 Database has {len(data)} contacts:")
                for c in data:
                    enabled = "Enabled" if c.get("enabled") else "Disabled"
                    print(f"  - @{c['username']} ({c.get('display_name', 'N/A')}) [{enabled}]")
                return True
            else:
                print(f"[Verify] FAIL - Unexpected response format")
                return False
    except Exception as e:
        print(f"[Verify] FAIL - Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("TikTok Streak - Contact Sync Tool")
    print("=" * 50)
    
    if sync_contacts():
        verify_contacts()
    
    print("\nDone!")
