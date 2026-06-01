import os
import argparse
from dotenv import load_dotenv
from utils import init_browser, login_tiktok, resolve_contacts_flow, load_contacts

# Load environment variables
load_dotenv()

def main():
    parser = argparse.ArgumentParser(description="TikTok Streak Auto - Phase 2 CLI")
    parser.add_argument("--send", action="store_true", help="Send messages to enabled contacts (Default)")
    parser.add_argument("--resolve-contacts", action="store_true", help="Scan TikTok inbox and resolve contact IDs/names")
    parser.add_argument("--debug-screenshots", action="store_true", help="Enable verbose debug screenshots")
    parser.add_argument("--debug-html", action="store_true", help="Enable saving HTML snapshots on error")
    
    args = parser.parse_args()
    
    # Default action is sending if not resolving
    is_resolve = args.resolve_contacts
    is_send = args.send or not is_resolve
    
    # Export debug flags to environment variables so utils.py can read them
    if args.debug_screenshots:
        os.environ["DEBUG_SCREENSHOTS"] = "true"
        print("[CLI] Verbose debug screenshots enabled.")
    if args.debug_html:
        os.environ["DEBUG_HTML"] = "true"
        print("[CLI] HTML snapshots on failure enabled.")
        
    print("[CLI] Initializing browser...")
    browser, wait = init_browser()
    
    try:
        # Perform login
        username = os.getenv("TIKTOK_USERNAME")
        password = os.getenv("TIKTOK_PASSWORD")
        if not username or not password:
            print("[CLI] Error: TIKTOK_USERNAME or TIKTOK_PASSWORD not set in environment.")
            browser.quit()
            return
            
        print(f"[CLI] Logging in as {username}...")
        login_tiktok(browser, wait, username, password)
        
        # Ensure migration happens if contacts.json doesn't exist yet
        load_contacts()
        
        if is_resolve:
            print("[CLI] Starting Contact Resolution Flow...")
            result = resolve_contacts_flow(browser, wait)
            print(f"[CLI] Contact Resolution completed: {result}")
            
        if is_send:
            print("[CLI] Starting Auto Send Message Flow...")
            # We import send flow dynamically from utils
            from utils import send_messages_flow
            result = send_messages_flow(browser, wait)
            print(f"[CLI] Auto Send Message completed: {result}")
            
    except Exception as e:
        print(f"[CLI] Fatal error during execution: {e}")
    finally:
        print("[CLI] Quitting browser...")
        try:
            browser.quit()
        except:
            pass

if __name__ == "__main__":
    main()
