from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time, re, csv, os, json
from datetime import datetime
from dotenv import load_dotenv
try:
    from ocacaptcha import oca_solve_captcha
except ImportError:
    oca_solve_captcha = None

load_dotenv()


def init_browser(headless=True):
    from config import USER_AGENT
    chrome_options = Options()
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument(f"user-agent={USER_AGENT}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    if headless:
        chrome_options.add_argument("--headless=new")
    browser = webdriver.Chrome(options=chrome_options)
    
    # Xoá flag navigator.webdriver để tránh bị TikTok phát hiện bot
    try:
        browser.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
    except:
        pass

    wait = WebDriverWait(browser, 20)

    return browser, wait


def save_cookies(browser, filepath):
    try:
        cookies = browser.get_cookies()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=4)
        print(f"[Cookies] Đã lưu cookies đăng nhập vào {filepath}")
    except Exception as e:
        print(f"[Cookies] Lỗi khi lưu cookies: {e}")

def load_cookies(browser, filepath):
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                cookies_data = json.load(f)
            
            if isinstance(cookies_data, dict) and "cookies" in cookies_data:
                cookies = cookies_data["cookies"]
            elif isinstance(cookies_data, list):
                cookies = cookies_data
            else:
                print(f"[Cookies] Định dạng file cookies không hợp lệ: {filepath}")
                return False
                
            for cookie in cookies:
                try:
                    # Chuyển đổi hạn dùng nếu cần thiết
                    if 'expirationDate' in cookie and 'expiry' not in cookie:
                        cookie['expiry'] = int(cookie['expirationDate'])
                    if 'expiry' in cookie:
                        cookie['expiry'] = int(cookie['expiry'])

                    # Chuẩn hóa SameSite để tránh lỗi Assertion của Selenium
                    if 'sameSite' in cookie:
                        val = str(cookie['sameSite']).lower()
                        if val == 'lax':
                            cookie['sameSite'] = 'Lax'
                        elif val == 'strict':
                            cookie['sameSite'] = 'Strict'
                        elif val in ('none', 'no_restriction'):
                            cookie['sameSite'] = 'None'
                        else:
                            # Xoá sameSite nếu không hợp lệ để Selenium/Chrome tự quyết định
                            del cookie['sameSite']
                            
                    browser.add_cookie(cookie)
                except Exception as e:
                    print(f"[Cookies Warning] Lỗi khi thêm cookie {cookie.get('name')}: {e}")
            print(f"[Cookies] Đã nạp cookies thành công từ {filepath}")
            return True
    except Exception as e:
        print(f"[Cookies] Lỗi khi nạp cookies: {e}")
    return False

def login_tiktok(browser, wait, username, password):
    from config import COOKIES_FILE
    
    # 1. Thử đăng nhập bằng cookies trước để tránh Captcha
    if os.path.exists(COOKIES_FILE):
        print("[Login] Tìm thấy cookies.json, tiến hành nạp phiên đăng nhập cũ...")
        browser.get('https://www.tiktok.com')
        time.sleep(3)
        try:
            browser.delete_all_cookies()  # Xoá cookies mặc định tránh xung đột
        except:
            pass
        if load_cookies(browser, COOKIES_FILE):
            browser.get('https://www.tiktok.com/messages?lang=vi')
            time.sleep(5)
            if is_logged_in(browser):
                print("[Login] Đăng nhập bằng COOKIES THÀNH CÔNG!")
                return
            else:
                print("[Login] Cookies hết hạn hoặc không hợp lệ. Đang chuyển sang đăng nhập bằng mật khẩu...")
                try:
                    save_debug_info(browser, "cookie_login_failed", save_html=True)
                except:
                    pass

    # 2. Đăng nhập bằng form nếu không có cookies/cookies hết hạn
    print("[Login] Bắt đầu điều hướng tới trang đăng nhập TikTok...")
    browser.get('https://www.tiktok.com/login/phone-or-email/email')
    
    actions = ActionChains(browser, duration=550)

    try:
        wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(username)
        password_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="new-password"]')))
        password_field.send_keys(password)
        wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "tiktok-11sviba-Button-StyledButton"))).click()
        time.sleep(5)
        
        user_api_key = os.getenv('CAPTCHA_API_KEY')
        number_captcha_attempts = 10
        action_type = 'tiktokcircle'
        if oca_solve_captcha and user_api_key:
            print(f"[Captcha] Đang giải captcha tự động với khóa: {user_api_key[:5]}...")
            oca_solve_captcha(browser, actions, user_api_key, action_type, number_captcha_attempts)
        else:
            print("[Warning] Bỏ qua giải Captcha tự động (chưa cài thư viện hoặc thiếu CAPTCHA_API_KEY).")
            print("👉 Vui lòng đăng nhập thủ công trên trình duyệt local để sinh file cookies.json.")
            
        time.sleep(5)
    except Exception as e:
        print(f"[Login] Lỗi khi điền form đăng nhập: {e}")

    # Kiểm tra xem đã đăng nhập thành công chưa để lưu lại cookies
    if is_logged_in(browser):
        print("[Login] Đăng nhập bằng form THÀNH CÔNG! Đang lưu cookies mới...")
        save_cookies(browser, COOKIES_FILE)
    else:
        print("[Login] Chưa đăng nhập được tài khoản.")



def get_all_friends(browser, wait):
    return resolve_contacts_flow(browser, wait)


def auto_send_message(browser, wait):
    return send_messages_flow(browser, wait)

import urllib.request
import urllib.parse

def send_telegram_message(token, chat_id, text):
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read()
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

def save_debug_info(browser, prefix, save_html=False):
    os.makedirs("logs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = f"logs/{prefix}_{timestamp}.png"
    try:
        browser.save_screenshot(screenshot_path)
        print(f"[Debug] Saved screenshot: {screenshot_path}")
    except Exception as e:
        print(f"[Debug] Failed to save screenshot: {e}")
        
    if save_html:
        html_path = f"logs/{prefix}_{timestamp}.html"
        try:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(browser.page_source)
            print(f"[Debug] Saved HTML: {html_path}")
        except Exception as e:
            print(f"[Debug] Failed to save HTML: {e}")

def handle_send_failure(browser, username, reason):
    print(f"[Failure] Failed to send message to @{username}. Reason: {reason}")
    save_html = os.getenv("DEBUG_HTML", "false").lower() == "true"
    save_debug_info(browser, f"error_{username}_{reason}", save_html=save_html)

def send_telegram_summary(stats, total_enabled):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[Telegram] Telegram credentials not set. Skipping notification.")
        return
        
    successes = [s for s in stats if s["success"]]
    failures = [s for s in stats if not s["success"]]
    
    message = "🔔 *TikTok Streak Auto Report* 🔔\n\n"
    message += f"📊 *Trạng thái:* {len(successes)}/{total_enabled} thành công\n"
    
    if successes:
        message += "\n✅ *Thành công:*\n"
        for s in successes:
            message += f"- @{s['username']} ({s['display_name']})\n"
            
    if failures:
        message += "\n❌ *Thất bại:*\n"
        for f in failures:
            message += f"- @{f['username']} ({f['display_name']}): `{f['reason']}`\n"
            
    message += f"\n🕒 *Thời gian:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    send_telegram_message(token, chat_id, message)

def send_and_verify_message(browser, wait, message, contact_username):
    input_selectors = [
        (By.CSS_SELECTOR, "div[contenteditable='true'][class*='public-DraftStyleDefault-block']"),
        (By.CSS_SELECTOR, "div[class*='public-DraftStyleDefault-block']"),
        (By.CSS_SELECTOR, "[data-e2e='message-input']"),
        (By.CSS_SELECTOR, "div[contenteditable='true']"),
    ]
    message_input = None
    for by, selector in input_selectors:
        try:
            message_input = wait.until(EC.presence_of_element_located((by, selector)))
            if message_input:
                break
        except:
            continue
            
    if not message_input:
        print(f"[Send] Error: Message input field not found for @{contact_username}")
        return False, "input_missing"
        
    try:
        message_input.click()
        time.sleep(0.5)
        message_input.send_keys(message)
        time.sleep(1)
        
        message_input.send_keys(Keys.RETURN)
        time.sleep(2)
        
        # Verify
        input_cleared = False
        try:
            for by, selector in input_selectors:
                try:
                    message_input = browser.find_element(by, selector)
                    if message_input:
                        break
                except:
                    continue
            if message_input:
                text_remaining = message_input.text.strip()
                if not text_remaining or text_remaining == "":
                    input_cleared = True
        except:
            input_cleared = True
            
        message_appeared = False
        try:
            message_elements = browser.find_elements(By.XPATH, f"//*[contains(text(), '{message}')]")
            if message_elements:
                message_appeared = True
        except:
            pass
            
        if input_cleared or message_appeared:
            print(f"[Send] Message verified successfully for @{contact_username}!")
            return True, "success"
        else:
            print(f"[Send] Verification failed for @{contact_username}")
            return False, "verify_failed"
            
    except Exception as e:
        print(f"[Send Error] Exception sending to @{contact_username}: {e}")
        return False, "send_button_missing"

def click_chat_by_name(browser, name):
    elements = find_chat_nickname_elements(browser)
    for el in elements:
        try:
            if el.text.strip() == name:
                el.click()
                return True
        except:
            continue
    return False

def send_messages_flow(browser, wait):
    print("[Send Flow] Starting auto-send flow...")
    browser.get('https://www.tiktok.com/messages?lang=vi')
    time.sleep(5)
    
    if not is_logged_in(browser):
        print("[Send Flow] Error: Cookie expired or not logged in.")
        send_telegram_message(
            os.getenv("TELEGRAM_BOT_TOKEN"),
            os.getenv("TELEGRAM_CHAT_ID"),
            "⚠️ *TikTok Streak Auto* ⚠️\n\n❌ Lỗi: Cookie hết hạn hoặc chưa đăng nhập. Không thể gửi tin nhắn!"
        )
        return {"status": "failed", "reason": "cookie_expired"}

    contacts = load_contacts()
    enabled_contacts = [c for c in contacts if c.get("enabled", True)]
    
    if not enabled_contacts:
        print("[Send Flow] No enabled contacts found. Skipping.")
        return {"status": "success", "sent_count": 0}
        
    message_text = os.getenv("MESSAGE", "streak")
    stats = []
    sent_usernames = set()
    
    print("[Send Flow] Fast-match: scanning visible sidebar chats...")
    for _ in range(3):
        scroll_chat_list(browser)
        time.sleep(1)
        
    for pass_num in range(2):
        sidebar_elements = find_chat_nickname_elements(browser)
        sidebar_names = [el.text.strip() for el in sidebar_elements if el.text.strip()]
        
        for name in sidebar_names:
            matched_contact = None
            for c in enabled_contacts:
                if c["username"] in sent_usernames:
                    continue
                if c["display_name"] == name or name in c.get("aliases", []) or c["username"] == name:
                    matched_contact = c
                    break
                    
            if matched_contact:
                username = matched_contact["username"]
                print(f"[Send Flow] Fast-match found chat for @{username} (Display name: '{name}')")
                
                if click_chat_by_name(browser, name):
                    time.sleep(2)
                    active_href, active_username = extract_active_chat_profile(browser)
                    active_conv_id = extract_conversation_id(browser)
                    
                    verified = False
                    if active_username and active_username.lower() == username.lower():
                        verified = True
                    elif active_conv_id and active_conv_id == matched_contact.get("conversation_id"):
                        verified = True
                    elif not active_username:
                        verified = True
                        
                    if verified:
                        success, reason = send_and_verify_message(browser, wait, message_text, username)
                        stat = {
                            "username": username,
                            "display_name": matched_contact["display_name"],
                            "success": success,
                            "reason": reason
                        }
                        stats.append(stat)
                        sent_usernames.add(username)
                        
                        matched_contact["last_sent"] = "success" if success else "failed"
                        matched_contact["last_sent_at"] = datetime.now().isoformat()
                        if success:
                            matched_contact["success_count"] = matched_contact.get("success_count", 0) + 1
                        else:
                            matched_contact["failure_count"] = matched_contact.get("failure_count", 0) + 1
                            handle_send_failure(browser, username, reason)
                        save_contacts(contacts)
                    else:
                        print(f"[Send Flow] Verification failed before sending: Scraped username @{active_username} does not match target @{username}")
                        
    remaining_targets = [c for c in enabled_contacts if c["username"] not in sent_usernames]
    if remaining_targets:
        print(f"[Send Flow] Slow-match: scrolling to find remaining {len(remaining_targets)} contacts...")
        scroll_attempts = 12
        clicked_indices = set()
        
        for scroll_i in range(scroll_attempts):
            scroll_chat_list(browser)
            time.sleep(1.5)
            
            sidebar_elements = find_chat_nickname_elements(browser)
            for idx, el in enumerate(sidebar_elements):
                if idx in clicked_indices:
                    continue
                
                try:
                    sidebar_elements = find_chat_nickname_elements(browser)
                    if idx >= len(sidebar_elements):
                        break
                    
                    name_in_sidebar = sidebar_elements[idx].text.strip()
                    if not name_in_sidebar:
                        continue
                        
                    sidebar_elements[idx].click()
                    clicked_indices.add(idx)
                    time.sleep(2)
                    
                    active_href, active_username = extract_active_chat_profile(browser)
                    active_conv_id = extract_conversation_id(browser)
                    user_id, sec_uid = extract_ids_from_page(browser)
                    
                    scraped_info = {
                        "username": active_username,
                        "display_name": name_in_sidebar,
                        "profile_url": active_href,
                        "conversation_id": active_conv_id,
                        "user_id": user_id,
                        "sec_uid": sec_uid
                    }
                    
                    matched_target = None
                    for c in remaining_targets:
                        if active_username and c["username"].lower() == active_username.lower():
                            matched_target = c
                            break
                        if active_conv_id and c.get("conversation_id") == active_conv_id:
                            matched_target = c
                            break
                        if (user_id and c.get("user_id") == user_id) or (sec_uid and c.get("sec_uid") == sec_uid):
                            matched_target = c
                            break
                            
                    if matched_target:
                        target_username = matched_target["username"]
                        print(f"[Send Flow] Slow-match found contact @{target_username} by ID or profile!")
                        
                        success, reason = send_and_verify_message(browser, wait, message_text, target_username)
                        update_contact_in_list(contacts, scraped_info)
                        
                        stat = {
                            "username": target_username,
                            "display_name": matched_target["display_name"],
                            "success": success,
                            "reason": reason
                        }
                        stats.append(stat)
                        sent_usernames.add(target_username)
                        
                        matched_target["last_sent"] = "success" if success else "failed"
                        matched_target["last_sent_at"] = datetime.now().isoformat()
                        if success:
                            matched_target["success_count"] = matched_target.get("success_count", 0) + 1
                        else:
                            matched_target["failure_count"] = matched_target.get("failure_count", 0) + 1
                            handle_send_failure(browser, target_username, reason)
                        save_contacts(contacts)
                        
                        remaining_targets = [c for c in enabled_contacts if c["username"] not in sent_usernames]
                        if not remaining_targets:
                            break
                except Exception as ex:
                    print(f"[Send Flow Debug] Error checking sidebar index {idx}: {ex}")
                    continue
            
            if not remaining_targets:
                break
                
    for c in enabled_contacts:
        if c["username"] not in sent_usernames:
            stat = {
                "username": c["username"],
                "display_name": c["display_name"],
                "success": False,
                "reason": "not_found"
            }
            stats.append(stat)
            c["last_sent"] = "failed"
            c["last_sent_at"] = datetime.now().isoformat()
            c["failure_count"] = c.get("failure_count", 0) + 1
            save_contacts(contacts)
            
    send_telegram_summary(stats, len(enabled_contacts))
    
    success_count = sum(1 for s in stats if s["success"])
    print(f"[Send Flow] Completed. Success: {success_count}/{len(enabled_contacts)}")
    return {
        "status": "success",
        "sent_count": success_count,
        "total_enabled": len(enabled_contacts),
        "details": stats
    }

CONTACTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contacts.json")
FRIENDS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "friends.csv")

def get_default_contact(username, display_name=None):
    return {
        "username": username,
        "display_name": display_name or username,
        "aliases": [],
        "profile_url": f"https://www.tiktok.com/@{username}",
        "user_id": None,
        "sec_uid": None,
        "conversation_id": None,
        "last_resolved_at": None,
        "resolve_confidence": "low",
        "last_sent": None,
        "last_sent_at": None,
        "success_count": 0,
        "failure_count": 0,
        "enabled": True
    }

def load_contacts():
    api_base_url = os.getenv("API_BASE_URL")
    api_key = os.getenv("API_KEY")
    
    if api_base_url and api_key:
        # Load from remote database via PHP API Proxy
        if not api_base_url.endswith('.php') and 'api.php' not in api_base_url:
            url = f"{api_base_url.rstrip('/')}/api.php?action=get_contacts"
        else:
            sep = "&" if "?" in api_base_url else "?"
            url = f"{api_base_url}{sep}action=get_contacts"

        print(f"[Remote DB] Fetching contacts from {url}...")
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "x-api-key": api_key,
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                }
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
                if isinstance(data, list):
                    normalized = []
                    for c in data:
                        if "aliases" in c and isinstance(c["aliases"], str):
                            try:
                                c["aliases"] = json.loads(c["aliases"])
                            except:
                                c["aliases"] = []
                        elif "aliases" not in c or not isinstance(c["aliases"], list):
                            c["aliases"] = []
                        
                        # Handle fields correctly as they might be stored as numeric or string in MySQL
                        c["enabled"] = bool(int(c.get("enabled", 1)))
                        c["success_count"] = int(c.get("success_count", 0))
                        c["failure_count"] = int(c.get("failure_count", 0))
                        normalized.append(c)
                    return normalized
                else:
                    print(f"[Remote DB Error] Invalid API response format (expected list): {data}")
        except Exception as e:
            print(f"[Remote DB Error] Failed to load contacts from API: {e}")
            print("[Remote DB] Falling back to local contacts.json...")

    # If contacts.json exists, load it
    if os.path.exists(CONTACTS_FILE):
        try:
            with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Error] Failed to load {CONTACTS_FILE}: {e}")
            return []
            
    # Migration logic from friends.csv
    contacts = []
    if os.path.exists(FRIENDS_CSV):
        print(f"[Migration] Migrating friends from {FRIENDS_CSV} to {CONTACTS_FILE}...")
        try:
            with open(FRIENDS_CSV, mode='r', newline='', encoding="utf-8") as file:
                reader = csv.DictReader(file)
                if reader.fieldnames and 'Username' in reader.fieldnames:
                    for row in reader:
                        username = row['Username'].strip()
                        if username:
                            contacts.append(get_default_contact(username))
            save_contacts(contacts)
            print(f"[Migration] Successfully migrated {len(contacts)} contacts.")
        except Exception as e:
            print(f"[Migration Error] Failed to migrate CSV: {e}")
            
    return contacts

def save_contacts(contacts):
    api_base_url = os.getenv("API_BASE_URL")
    api_key = os.getenv("API_KEY")
    
    # Save to local file regardless, as a backup cache
    try:
        with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
            json.dump(contacts, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Error] Failed to save {CONTACTS_FILE}: {e}")

    if api_base_url and api_key:
        if not api_base_url.endswith('.php') and 'api.php' not in api_base_url:
            url = f"{api_base_url.rstrip('/')}/api.php?action=save_contacts"
        else:
            sep = "&" if "?" in api_base_url else "?"
            url = f"{api_base_url}{sep}action=save_contacts"

        print(f"[Remote DB] Saving contacts to {url}...")
        try:
            payload = json.dumps(contacts).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                if res_data.get("status") == "success":
                    print("[Remote DB] Successfully saved contacts to database.")
                else:
                    print(f"[Remote DB Error] API save failed: {res_data}")
        except Exception as e:
            print(f"[Remote DB Error] Failed to save contacts to API: {e}")

def update_contact_in_list(contacts, scraped_info):
    """
    Updates or inserts a contact in the contacts list based on scraped info.
    Returns (updated_contact, is_new)
    """
    scraped_username = scraped_info.get("username")
    scraped_display_name = scraped_info.get("display_name")
    scraped_profile_url = scraped_info.get("profile_url")
    scraped_conv_id = scraped_info.get("conversation_id")
    scraped_user_id = scraped_info.get("user_id")
    scraped_sec_uid = scraped_info.get("sec_uid")
    
    matched_contact = None
    confidence = "low"
    
    # 1. Match by conversation_id
    if scraped_conv_id:
        for c in contacts:
            if c.get("conversation_id") == scraped_conv_id:
                matched_contact = c
                confidence = "high"
                break
                
    # 2. Match by user_id or sec_uid
    if not matched_contact and (scraped_user_id or scraped_sec_uid):
        for c in contacts:
            if (scraped_user_id and c.get("user_id") == scraped_user_id) or \
               (scraped_sec_uid and c.get("sec_uid") == scraped_sec_uid):
                matched_contact = c
                confidence = "high"
                break
                
    # 3. Match by profile_url or username (or aliases)
    if not matched_contact and scraped_username:
        for c in contacts:
            if c.get("username") == scraped_username or \
               scraped_username in c.get("aliases", []) or \
               (c.get("profile_url") and f"/@{scraped_username}" in c.get("profile_url")):
                matched_contact = c
                confidence = "high"
                break
                
    # 4. Match by display name or aliases
    if not matched_contact and scraped_display_name:
        for c in contacts:
            if c.get("display_name") == scraped_display_name or \
               scraped_display_name in c.get("aliases", []):
                matched_contact = c
                confidence = "medium"
                break

    is_new = False
    if not matched_contact:
        # Create a new disabled contact for auto-discovery
        if scraped_username:
            matched_contact = get_default_contact(scraped_username, scraped_display_name)
            matched_contact["enabled"] = False  # Keep disabled by default
            contacts.append(matched_contact)
            is_new = True
            confidence = "high"
        else:
            # Cannot create contact without username
            return None, False

    # Update fields
    if scraped_username and matched_contact["username"] != scraped_username:
        if matched_contact["username"] not in matched_contact["aliases"]:
            matched_contact["aliases"].append(matched_contact["username"])
        matched_contact["username"] = scraped_username
        
    if scraped_display_name and matched_contact["display_name"] != scraped_display_name:
        if matched_contact["display_name"] not in matched_contact["aliases"]:
            matched_contact["aliases"].append(matched_contact["display_name"])
        matched_contact["display_name"] = scraped_display_name
        
    if scraped_profile_url:
        matched_contact["profile_url"] = scraped_profile_url
    elif scraped_username and not matched_contact.get("profile_url"):
        matched_contact["profile_url"] = f"https://www.tiktok.com/@{scraped_username}"
        
    if scraped_conv_id:
        matched_contact["conversation_id"] = scraped_conv_id
    if scraped_user_id:
        matched_contact["user_id"] = scraped_user_id
    if scraped_sec_uid:
        matched_contact["sec_uid"] = scraped_sec_uid
        
    matched_contact["last_resolved_at"] = datetime.now().isoformat()
    matched_contact["resolve_confidence"] = confidence
    
    return matched_contact, is_new

def is_logged_in(browser):
    current_url = browser.current_url
    if "/login" in current_url:
        return False
    try:
        if browser.find_elements(By.CSS_SELECTOR, "[class*='Nickname']") or \
           browser.find_elements(By.CSS_SELECTOR, "a[href*='/@']") or \
           browser.find_elements(By.CSS_SELECTOR, "[class*='DraftStyleDefault']"):
            return True
    except:
        pass
    return "/login" not in current_url

def find_chat_nickname_elements(browser):
    selectors = [
        (By.CSS_SELECTOR, "div[class*='PInfoNickname']"),
        (By.CSS_SELECTOR, "span[class*='PInfoNickname']"),
        (By.CSS_SELECTOR, "div[class*='Nickname']"),
        (By.XPATH, "//*[contains(@class, 'Nickname')]"),
        (By.CLASS_NAME, "css-1mez8np-PInfoNickname"),
        (By.CLASS_NAME, "css-2tydh5-PInfoNickname"),
    ]
    for by, selector in selectors:
        try:
            elements = browser.find_elements(by, selector)
            if elements:
                filtered = [el for el in elements if el.text.strip()]
                if filtered:
                    return filtered
        except:
            continue
    return []

def scroll_chat_list(browser):
    js_scroll = """
    let scrollable = document.querySelector('div[class*="DivSideNav"]') || 
                     document.querySelector('div[class*="SideNav"]') ||
                     document.querySelector('[class*="MessageList"]') ||
                     document.querySelector('[class*="ConversationList"]') ||
                     document.querySelector('[class*="ScrollContainer"]');
    if (!scrollable) {
        let nick = document.querySelector('[class*="Nickname"]');
        if (nick) {
            let p = nick.parentElement;
            while (p && p !== document.body) {
                let style = window.getComputedStyle(p);
                if (style.overflowY === 'scroll' || style.overflowY === 'auto' || p.scrollHeight > p.clientHeight) {
                    scrollable = p;
                    break;
                }
                p = p.parentElement;
            }
        }
    }
    if (scrollable) {
        let old_top = scrollable.scrollTop;
        scrollable.scrollTop = scrollable.scrollHeight;
        return {
            "success": true, 
            "scrolled": scrollable.scrollTop > old_top,
            "height": scrollable.scrollHeight
        }
    }
    return {"success": false};
    """
    try:
        return browser.execute_script(js_scroll)
    except Exception as e:
        print(f"[Debug] Scroll script error: {e}")
        return {"success": False}

def extract_active_chat_profile(browser):
    selectors = [
        (By.CSS_SELECTOR, "a[class*='StyledLink'][href*='/@']"),
        (By.CSS_SELECTOR, "div[class*='ChatHeader'] a[href*='/@']"),
        (By.CSS_SELECTOR, "div[class*='Header'] a[href*='/@']"),
        (By.CSS_SELECTOR, "a[href*='/@']"),
        (By.CLASS_NAME, "css-1qxabns-StyledLink"),
    ]
    my_username = os.getenv("TIKTOK_USERNAME")
    for by, selector in selectors:
        try:
            elements = browser.find_elements(by, selector)
            for el in elements:
                href = el.get_attribute("href")
                if href and "/@" in href:
                    username_match = re.search(r"/@([^/?#]+)", href)
                    if username_match:
                        username = username_match.group(1)
                        if my_username and username.lower() == my_username.lower():
                            continue
                        return href, username
        except:
            continue
    return None, None

def extract_active_chat_display_name(browser, profile_element_text=None):
    if profile_element_text:
        display_name = profile_element_text.strip()
        if display_name:
            return display_name
            
    selectors = [
        (By.CSS_SELECTOR, "div[class*='ChatHeader'] div[class*='Title']"),
        (By.CSS_SELECTOR, "div[class*='ChatHeader'] span[class*='Nickname']"),
        (By.CSS_SELECTOR, "div[class*='Header'] h1"),
        (By.CSS_SELECTOR, "div[class*='Header'] h2"),
        (By.CSS_SELECTOR, "div[class*='Header'] span"),
    ]
    for by, selector in selectors:
        try:
            el = browser.find_element(by, selector)
            text = el.text.strip()
            if text:
                return text
        except:
            continue
    return None

def extract_conversation_id(browser):
    try:
        current_url = browser.current_url
        match = re.search(r"[?&](roomId|room_id|conversation_id)=([^&]+)", current_url)
        if match:
            return match.group(2)
    except Exception as e:
        print(f"[Debug] Error parsing URL for room ID: {e}")
    return None

def extract_ids_from_page(browser):
    js_script = """
    try {
        let result = {user_id: null, sec_uid: null};
        const scripts = Array.from(document.querySelectorAll('script'));
        for (const s of scripts) {
            const content = s.textContent;
            if (content.includes('secUid') || content.includes('userId') || content.includes('sec_uid') || content.includes('user_id')) {
                let secMatch = content.match(/"secUid"\\s*:\\s*"([^"]+)"/) || content.match(/"sec_uid"\\s*:\\s*"([^"]+)"/);
                let userMatch = content.match(/"userId"\\s*:\\s*"([^"]+)"/) || content.match(/"user_id"\\s*:\\s*"([^"]+)"/);
                if (secMatch) result.sec_uid = secMatch[1];
                if (userMatch) result.user_id = userMatch[1];
                
                if (result.sec_uid && result.user_id) break;
            }
        }
        if (!result.user_id || !result.sec_uid) {
            const elements = Array.from(document.querySelectorAll('*'));
            for (const el of elements) {
                for (const attr of el.attributes) {
                    if (attr.name.includes('user-id') || attr.name.includes('userid')) {
                        result.user_id = attr.value;
                    }
                    if (attr.name.includes('sec-uid') || attr.name.includes('secuid')) {
                        result.sec_uid = attr.value;
                    }
                }
            }
        }
        return result;
    } catch(e) {
        return {error: e.message};
    }
    """
    try:
        res = browser.execute_script(js_script)
        if res and "error" not in res:
            return res.get("user_id"), res.get("sec_uid")
    except Exception as e:
        print(f"[Debug] JS extraction error: {e}")
    return None, None

def resolve_contacts_flow(browser, wait):
    print("[Resolver] Navigating to messages...")
    browser.get('https://www.tiktok.com/messages?lang=vi')
    time.sleep(5)
    
    if not is_logged_in(browser):
        print("[Resolver] Error: Cookie expired or not logged in.")
        return {"status": "failed", "reason": "cookie_expired"}

    contacts = load_contacts()
    
    print("[Resolver] Scrolling chat sidebar to load all conversations...")
    last_height = 0
    scroll_attempts = 15
    for i in range(scroll_attempts):
        res = scroll_chat_list(browser)
        if not res or not res.get("success"):
            print("[Resolver] Could not find scrollable sidebar, skipping scroll...")
            break
        current_height = res.get("height", 0)
        print(f"[Resolver] Scroll loop {i+1}/{scroll_attempts}, height: {current_height}")
        time.sleep(1.5)
        if current_height == last_height:
            break
        last_height = current_height

    all_users = find_chat_nickname_elements(browser)
    print(f"[Resolver] Found {len(all_users)} chat conversations in sidebar.")
    
    resolved_count = 0
    new_discovered_count = 0
    
    for index in range(len(all_users)):
        try:
            all_users = find_chat_nickname_elements(browser)
            if index >= len(all_users):
                break
                
            user_el = all_users[index]
            sidebar_name = user_el.text.strip()
            if not sidebar_name:
                continue
                
            # Click chat to open
            user_el.click()
            time.sleep(2)
            
            profile_url, username = extract_active_chat_profile(browser)
            if not username:
                print(f"[Resolver] Warning: Could not resolve username for sidebar chat: '{sidebar_name}'")
                continue
                
            display_name = extract_active_chat_display_name(browser, sidebar_name)
            conversation_id = extract_conversation_id(browser)
            user_id, sec_uid = extract_ids_from_page(browser)
            
            scraped_info = {
                "username": username,
                "display_name": display_name or sidebar_name,
                "profile_url": profile_url,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "sec_uid": sec_uid
            }
            
            contact, is_new = update_contact_in_list(contacts, scraped_info)
            if contact:
                resolved_count += 1
                if is_new:
                    new_discovered_count += 1
                    print(f"[Resolver] Discovered new contact: @{username} ({display_name})")
                else:
                    print(f"[Resolver] Resolved contact: @{username} ({display_name}) [ID: {user_id or 'N/A'}]")
                    
                save_contacts(contacts)
                
        except Exception as e:
            print(f"[Resolver Error] Failed to resolve chat at index {index}: {e}")
            continue
            
    print(f"[Resolver] Finished. Resolved: {resolved_count}, New Discovered (disabled): {new_discovered_count}")
    return {
        "status": "success",
        "resolved_count": resolved_count,
        "new_discovered_count": new_discovered_count
    }



