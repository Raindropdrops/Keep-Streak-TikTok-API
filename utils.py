from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time, re, csv, os, json, random, sys
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
try:
    from ocacaptcha import oca_solve_captcha
except ImportError:
    oca_solve_captcha = None

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


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
        
        # Danh sách selector dự phòng cho nút đăng nhập (class TikTok hay thay đổi)
        login_button_selectors = [
            (By.CLASS_NAME, "tiktok-11sviba-Button-StyledButton"),
            (By.CSS_SELECTOR, "button[data-e2e='login-button']"),
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.XPATH, "//button[contains(@class,'Button') and not(@disabled)]"),
            (By.XPATH, "//form//button[last()]"),
        ]
        login_clicked = False
        for by, sel in login_button_selectors:
            try:
                btn = wait.until(EC.element_to_be_clickable((by, sel)))
                btn.click()
                login_clicked = True
                print(f"[Login] Nút đăng nhập đã được click (selector: {sel})")
                break
            except:
                continue
        if not login_clicked:
            print("[Login] Warning: Không tìm thấy nút đăng nhập bằng bất kỳ selector nào!")
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


# === HỆ THỐNG TIN NHẮN THÔNG MINH KHÔNG LẶP ===
MESSAGE_HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "message_history.json"
)

VIETNAM_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
DAY_MESSAGE_ENV = {
    0: "MESSAGE_MON",
    1: "MESSAGE_TUE",
    2: "MESSAGE_WED",
    3: "MESSAGE_THU",
    4: "MESSAGE_FRI",
    5: "MESSAGE_SAT",
    6: "MESSAGE_SUN",
}
DEFAULT_DAILY_MESSAGES = {
    0: [
        "Chúc bạn tuần mới nhiều năng lượng, mọi việc đều thuận lợi nhé!",
        "Tuần mới bắt đầu rồi, chúc bạn có thật nhiều niềm vui và may mắn!",
    ],
    1: [
        "Chúc bạn một ngày thứ Ba nhẹ nhàng, làm gì cũng suôn sẻ nhé!",
        "Hôm nay nhớ dành một chút thời gian nghỉ ngơi và chăm sóc bản thân nha!",
    ],
    2: [
        "Đã giữa tuần rồi, chúc bạn luôn giữ được năng lượng tích cực nhé!",
        "Chúc bạn một ngày bình an và có thêm nhiều niềm vui nho nhỏ!",
    ],
    3: [
        "Chúc bạn hôm nay làm việc hiệu quả và gặp nhiều chuyện dễ thương nhé!",
        "Cuối tuần đang đến gần rồi, cố gắng thêm một chút và nhớ nghỉ ngơi nha!",
    ],
    4: [
        "Thứ Sáu rồi, chúc bạn kết thúc tuần thật trọn vẹn và vui vẻ!",
        "Chúc bạn hôm nay nhiều niềm vui, tối đến được thư giãn thật thoải mái!",
    ],
    5: [
        "Cuối tuần rồi, chúc bạn có thời gian nghỉ ngơi và làm điều mình thích nhé!",
        "Chúc bạn một ngày thứ Bảy thật vui, nhẹ nhàng và nhiều tiếng cười!",
    ],
    6: [
        "Chủ Nhật bình yên nhé, mong bạn có một ngày thật thư thái bên những người thân yêu!",
        "Chúc bạn nghỉ ngơi thật tốt để sẵn sàng cho một tuần mới nhiều điều hay!",
    ],
}


def get_vietnam_now():
    return datetime.now(VIETNAM_TIMEZONE)


def _split_message_pool(value):
    return [message.strip() for message in value.split("|") if message.strip()]


def _load_message_history():
    """Đọc lịch sử tin nhắn đã gửi."""
    if os.path.exists(MESSAGE_HISTORY_FILE):
        try:
            with open(MESSAGE_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"[Message History] Lỗi đọc lịch sử: {e}")
    return []

def _save_message_history(history):
    """Ghi lịch sử, chỉ giữ 90 ngày gần nhất."""
    try:
        history_sorted = sorted(history, key=lambda x: x["date"], reverse=True)
        history_trimmed = history_sorted[:90]
        with open(MESSAGE_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_trimmed, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Message History] Lỗi ghi lịch sử: {e}")

def _get_message_pool(now=None):
    """Lấy pool theo đúng thứ tại Việt Nam, rồi mới dùng pool chung."""
    now = now or get_vietnam_now()
    day_env_name = DAY_MESSAGE_ENV[now.weekday()]
    day_value = os.getenv(day_env_name, "").strip()
    if day_value:
        pool = _split_message_pool(day_value)
        if pool:
            return pool

    pool_val = os.getenv("MESSAGES", "").strip()
    if pool_val:
        pool = _split_message_pool(pool_val)
        if pool:
            return pool

    legacy = os.getenv("MESSAGE", "").strip()
    if legacy:
        return [legacy]

    return DEFAULT_DAILY_MESSAGES[now.weekday()]

def get_message_for_today():
    """
    Chọn 1 tin nhắn mỗi ngày với cơ chế KHÔNG LẶP THÔNG MINH.

    Thuật toán:
      1. Nếu hôm nay đã có bản ghi → trả về câu đó (idempotent khi re-run).
      2. Tính cửa sổ tránh lặp = min(7, pool_size - 1).
         VD: 14 câu → không lặp trong 7 ngày; 4 câu → không lặp trong 3 ngày.
      3. Lọc bỏ các câu đã dùng trong cửa sổ đó.
      4. Random chọn 1 câu từ tập còn lại.
      5. Lưu lịch sử.
    """
    now = get_vietnam_now()
    today_str = now.strftime("%Y-%m-%d")
    history = _load_message_history()
    pool = _get_message_pool(now)

    # Bước 1: Idempotent — cùng ngày luôn trả về cùng câu
    for entry in history:
        if entry.get("date") == today_str:
            msg = entry.get("message", "")
            if msg in pool:
                print(f"[Message] Hôm nay ({today_str}) đã chọn: '{msg}'")
                return msg

    # Bước 2: Lấy pool và tính cửa sổ tránh lặp
    no_repeat_window = max(1, min(7, len(pool) - 1)) if len(pool) > 1 else 0
    print(f"[Message] Pool: {len(pool)} câu | Cửa sổ tránh lặp: {no_repeat_window} ngày")

    # Bước 3: Lọc các câu đã dùng gần đây
    recent_messages = set()
    if no_repeat_window > 0:
        recent_entries = sorted(history, key=lambda x: x["date"], reverse=True)
        same_pool_entries = [
            entry for entry in recent_entries if entry.get("message") in pool
        ]
        for entry in same_pool_entries[:no_repeat_window]:
            recent_messages.add(entry["message"])

    available = [m for m in pool if m not in recent_messages]

    # Nếu không còn câu nào (pool quá nhỏ) → dùng lại toàn bộ
    if not available:
        available = pool
        print("[Message] Đã dùng hết pool, reset và chọn lại từ đầu.")

    # Bước 4: Random chọn
    chosen = random.choice(available)
    print(f"[Message] Chọn: '{chosen}' ({len(available)}/{len(pool)} câu còn khả dụng)")

    # Bước 5: Lưu lịch sử
    history.append({"date": today_str, "message": chosen})
    _save_message_history(history)

    return chosen


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

def normalize_name(text):
    """Loại bỏ ký tự Unicode ẩn (zero-width, variation selectors) để so sánh chuỗi tên chính xác hơn."""
    # Loại bỏ các ký tự variation selector (U+FE00–U+FE0F) và zero-width
    invisible = [
        '\u200b', '\u200c', '\u200d', '\u200e', '\u200f',  # zero-width chars
        '\ufeff',                                             # BOM
        '\ufe0f', '\ufe0e',                                  # variation selectors
    ]
    result = text
    for ch in invisible:
        result = result.replace(ch, '')
    return result.strip()

def normalize_username(value):
    if not isinstance(value, str):
        return ""
    return normalize_name(value).lstrip("@").casefold()


def is_contact_enabled(contact):
    value = contact.get("enabled")
    return value is True or (
        isinstance(value, int) and not isinstance(value, bool) and value == 1
    )


def recipient_is_verified(contact, active_username, active_conv_id=None):
    expected_username = normalize_username(contact.get("username"))
    actual_username = normalize_username(active_username)
    if not expected_username or actual_username != expected_username:
        return False

    expected_conv_id = str(contact.get("conversation_id") or "").strip()
    actual_conv_id = str(active_conv_id or "").strip()
    if expected_conv_id and actual_conv_id and expected_conv_id != actual_conv_id:
        return False

    return True


def get_safe_enabled_contacts(contacts):
    username_counts = {}
    for contact in contacts:
        if not is_contact_enabled(contact):
            continue
        username = normalize_username(contact.get("username"))
        if username:
            username_counts[username] = username_counts.get(username, 0) + 1

    safe_contacts = []
    for contact in contacts:
        if not is_contact_enabled(contact):
            continue
        username = normalize_username(contact.get("username"))
        if not username:
            print("[Send Flow] SKIPPED enabled contact with missing/invalid username.")
            continue
        if username_counts.get(username) != 1:
            print(f"[Send Flow] SKIPPED duplicate enabled username: @{username}")
            continue
        safe_contacts.append(contact)
    return safe_contacts


def get_contact_sidebar_labels(contact, enabled_contacts):
    label_owners = {}
    for candidate in enabled_contacts:
        raw_labels = [
            candidate.get("username"),
            candidate.get("display_name"),
            *candidate.get("aliases", []),
        ]
        owner = normalize_username(candidate.get("username"))
        for raw_label in raw_labels:
            label = normalize_name(raw_label).casefold() if isinstance(raw_label, str) else ""
            if label:
                label_owners.setdefault(label, set()).add(owner)

    target_username = normalize_username(contact.get("username"))
    labels = set()
    raw_labels = [
        contact.get("username"),
        contact.get("display_name"),
        *contact.get("aliases", []),
    ]
    for raw_label in raw_labels:
        label = normalize_name(raw_label).casefold() if isinstance(raw_label, str) else ""
        if label and label_owners.get(label) == {target_username}:
            labels.add(label)
    return labels


def find_unique_chat_element(browser, contact, enabled_contacts):
    allowed_labels = get_contact_sidebar_labels(contact, enabled_contacts)
    if not allowed_labels:
        return None, "no_unique_sidebar_label"

    matches = []
    for element in find_chat_nickname_elements(browser):
        try:
            label = normalize_name(element.text).casefold()
            if label in allowed_labels:
                matches.append(element)
        except Exception:
            continue

    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, "ambiguous_sidebar_label"
    return None, "not_found"


def click_chat_element(browser, element):
    try:
        browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.5)
        browser.execute_script("arguments[0].click();", element)
        return True
    except Exception:
        return False


def wait_for_verified_recipient(browser, contact, timeout_seconds=8):
    deadline = time.time() + timeout_seconds
    consecutive_matches = 0
    last_profile = (None, None, None)

    while time.time() < deadline:
        active_href, active_username = extract_active_chat_profile(browser)
        active_conv_id = extract_conversation_id(browser)
        last_profile = (active_href, active_username, active_conv_id)
        if recipient_is_verified(contact, active_username, active_conv_id):
            consecutive_matches += 1
            if consecutive_matches >= 2:
                return True, last_profile
        else:
            consecutive_matches = 0
        time.sleep(0.5)

    return False, last_profile


def click_chat_by_name(browser, name):
    normalized_name = normalize_name(name)
    elements = find_chat_nickname_elements(browser)
    for el in elements:
        try:
            el_text = normalize_name(el.text)
            if el_text == normalized_name:
                # Cuộn phần tử vào giữa màn hình để đảm bảo nó hiển thị
                browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                time.sleep(0.5)
                # Click bằng JS để tránh bị che chắn hoặc lỗi click của Selenium
                browser.execute_script("arguments[0].click();", el)
                return True
        except Exception:
            # Stale element hoặc lỗi khác → thử phần tử tiếp
            continue
    return False

def _legacy_send_messages_flow_disabled(browser, wait):
    raise RuntimeError("Unsafe legacy send flow is disabled.")
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
        
    message_text = get_message_for_today()
    stats = []
    sent_usernames = set()
    
    print("[Send Flow] Fast-match: scanning visible sidebar chats...")
    for _ in range(3):
        scroll_chat_list(browser)
        time.sleep(1)
        
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
                # Chờ thêm để TikTok load xong profile header
                time.sleep(3)
                active_href, active_username = extract_active_chat_profile(browser)
                
                # Nếu lần đầu chưa lấy được username, thử lại sau 2 giây
                if not active_username:
                    time.sleep(2)
                    active_href, active_username = extract_active_chat_profile(browser)
                
                active_conv_id = extract_conversation_id(browser)
                
                verified = False
                if active_username and active_username.lower() == username.lower():
                    verified = True
                    print(f"[Send Flow] ✅ Verified by username: @{active_username}")
                elif active_conv_id and matched_contact.get("conversation_id") and active_conv_id == matched_contact.get("conversation_id"):
                    verified = True
                    print(f"[Send Flow] ✅ Verified by conversation_id: {active_conv_id}")
                else:
                    # KHÔNG gửi nếu không xác thực được đúng người
                    print(f"[Send Flow] ⛔ SKIPPED: Cannot verify chat is @{username}. "
                          f"Scraped username='{active_username}', conv_id='{active_conv_id}'. "
                          f"Expected username='{username}', conv_id='{matched_contact.get('conversation_id')}'. "
                          f"Bỏ qua để tránh gửi nhầm!")
                    
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
                        
                    el = sidebar_elements[idx]
                    browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                    time.sleep(0.5)
                    browser.execute_script("arguments[0].click();", el)
                    clicked_indices.add(idx)
                    # Chờ TikTok load profile header
                    time.sleep(3)
                    
                    active_href, active_username = extract_active_chat_profile(browser)
                    # Nếu chưa lấy được username, thử lại sau 2 giây
                    if not active_username:
                        time.sleep(2)
                        active_href, active_username = extract_active_chat_profile(browser)
                    
                    active_conv_id = extract_conversation_id(browser)
                    user_id, sec_uid = extract_ids_from_page(browser)
                    
                    # Nếu vẫn không lấy được bất kỳ thông tin định danh nào → bỏ qua
                    if not active_username and not active_conv_id and not user_id and not sec_uid:
                        print(f"[Send Flow] Slow-match: Cannot identify user for sidebar '{name_in_sidebar}'. Skipping to avoid wrong send.")
                        continue
                    
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

def send_messages_flow(browser, wait):
    print("[Send Flow] Starting strict recipient flow...")
    browser.get("https://www.tiktok.com/messages?lang=vi")
    time.sleep(5)

    if not is_logged_in(browser):
        print("[Send Flow] Error: Cookie expired or not logged in.")
        send_telegram_message(
            os.getenv("TELEGRAM_BOT_TOKEN"),
            os.getenv("TELEGRAM_CHAT_ID"),
            "TikTok Streak Auto: cookie expired or login failed. No messages sent.",
        )
        return {"status": "failed", "reason": "cookie_expired"}

    contacts = load_contacts()
    enabled_contacts = get_safe_enabled_contacts(contacts)
    if not enabled_contacts:
        print("[Send Flow] No explicitly enabled, uniquely identified contacts.")
        return {"status": "success", "sent_count": 0, "total_enabled": 0}

    message_text = get_message_for_today()
    stats = []
    sent_usernames = set()
    print("[Send Flow] Strict mode: exact username verification is mandatory.")

    for contact in enabled_contacts:
        username = contact["username"]
        active_href, active_username = extract_active_chat_profile(browser)
        active_conv_id = extract_conversation_id(browser)
        verified = recipient_is_verified(contact, active_username, active_conv_id)

        if not verified:
            element, find_reason = find_unique_chat_element(
                browser, contact, enabled_contacts
            )
            if element is None:
                print(f"[Send Flow] SKIPPED @{username}: {find_reason}")
                continue
            if not click_chat_element(browser, element):
                print(f"[Send Flow] SKIPPED @{username}: click_failed")
                continue

        verified, (_, active_username, active_conv_id) = (
            wait_for_verified_recipient(browser, contact)
        )
        if not verified:
            print(
                f"[Send Flow] SKIPPED @{username}: recipient_not_verified "
                f"(active_username={active_username!r}, "
                f"active_conv_id={active_conv_id!r})"
            )
            continue

        print(f"[Send Flow] Verified exact recipient: @{username}")
        success, reason = send_and_verify_message(
            browser, wait, message_text, username
        )
        stats.append({
            "username": username,
            "display_name": contact.get("display_name", username),
            "success": success,
            "reason": reason,
        })
        sent_usernames.add(username)

        contact["last_sent"] = "success" if success else "failed"
        contact["last_sent_at"] = datetime.now().isoformat()
        if success:
            contact["success_count"] = contact.get("success_count", 0) + 1
        else:
            contact["failure_count"] = contact.get("failure_count", 0) + 1
            handle_send_failure(browser, username, reason)
        save_contacts(contacts)

    for contact in enabled_contacts:
        if contact["username"] in sent_usernames:
            continue
        stats.append({
            "username": contact["username"],
            "display_name": contact.get("display_name", contact["username"]),
            "success": False,
            "reason": "recipient_not_verified",
        })

    send_telegram_summary(stats, len(enabled_contacts))
    success_count = sum(1 for stat in stats if stat["success"])
    print(f"[Send Flow] Completed. Success: {success_count}/{len(enabled_contacts)}")
    return {
        "status": "success",
        "sent_count": success_count,
        "total_enabled": len(enabled_contacts),
        "details": stats,
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
                        c["enabled"] = is_contact_enabled(c)
                        c["success_count"] = int(c.get("success_count", 0))
                        c["failure_count"] = int(c.get("failure_count", 0))
                        normalized.append(c)
                    return normalized
                else:
                    print(f"[Remote DB Error] Invalid API response format (expected list): {data}")
                    return []
        except Exception as e:
            print(f"[Remote DB Error] Failed to load contacts from API: {e}")
            print("[Remote DB] Refusing stale local fallback. No contacts will be used.")
            return []

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

def _legacy_update_contact_in_list_disabled(contacts, scraped_info):
    raise RuntimeError("Unsafe legacy contact matching is disabled.")
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


def update_contact_in_list(contacts, scraped_info):
    scraped_username = normalize_username(scraped_info.get("username"))
    if not scraped_username:
        return None, False

    matched_contact = None
    for contact in contacts:
        if normalize_username(contact.get("username")) == scraped_username:
            matched_contact = contact
            break

    is_new = matched_contact is None
    if is_new:
        matched_contact = get_default_contact(
            scraped_username, scraped_info.get("display_name")
        )
        matched_contact["enabled"] = False
        contacts.append(matched_contact)

    aliases = matched_contact.get("aliases")
    if not isinstance(aliases, list):
        aliases = []
        matched_contact["aliases"] = aliases

    scraped_display_name = scraped_info.get("display_name")
    current_display_name = matched_contact.get("display_name")
    if (
        isinstance(scraped_display_name, str)
        and scraped_display_name.strip()
        and scraped_display_name != current_display_name
    ):
        if current_display_name and current_display_name not in aliases:
            aliases.append(current_display_name)
        matched_contact["display_name"] = scraped_display_name

    profile_url = scraped_info.get("profile_url")
    if profile_url:
        matched_contact["profile_url"] = profile_url
    else:
        matched_contact["profile_url"] = f"https://www.tiktok.com/@{scraped_username}"

    for field in ("conversation_id", "user_id", "sec_uid"):
        value = scraped_info.get(field)
        if value:
            matched_contact[field] = value

    matched_contact["last_resolved_at"] = datetime.now().isoformat()
    matched_contact["resolve_confidence"] = "high"
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

def _legacy_extract_active_chat_profile_disabled(browser):
    raise RuntimeError("Unsafe page-wide profile extraction is disabled.")
    my_username = os.getenv("TIKTOK_USERNAME")
    
    # 1. Thử tìm trong các container tiêu đề chat trước (Ưu tiên cao nhất)
    header_selectors = [
        "div[class*='ChatHeader']",
        "div[class*='Header']",
        "[class*='ChatHeader']",
        "[class*='Header']",
    ]
    for container_sel in header_selectors:
        try:
            containers = browser.find_elements(By.CSS_SELECTOR, container_sel)
            for container in containers:
                links = container.find_elements(By.CSS_SELECTOR, "a[href*='/@']")
                for link in links:
                    href = link.get_attribute("href")
                    if href and "/@" in href:
                        username_match = re.search(r"/@([^/?#]+)", href)
                        if username_match:
                            username = username_match.group(1)
                            if my_username and username.lower() == my_username.lower():
                                continue
                            return href, username
        except:
            pass

    # 2. Fallback: Quét toàn bộ link profile trên trang nhưng loại trừ sidebar
    try:
        all_links = browser.find_elements(By.CSS_SELECTOR, "a[href*='/@']")
        for link in all_links:
            href = link.get_attribute("href")
            if not href or "/@" not in href:
                continue
                
            # Kiểm tra xem link này có nằm trong sidebar không
            is_in_sidebar = False
            try:
                # Đi ngược lên 5 cấp cha để kiểm tra class/id
                parent = link
                for _ in range(5):
                    parent = parent.find_element(By.XPATH, "..")
                    p_class = parent.get_attribute("class") or ""
                    p_id = parent.get_attribute("id") or ""
                    if any(x in p_class.lower() or x in p_id.lower() for x in ("sidebar", "chatlist", "list", "contact")):
                        is_in_sidebar = True
                        break
            except:
                pass
                
            if is_in_sidebar:
                continue
                
            username_match = re.search(r"/@([^/?#]+)", href)
            if username_match:
                username = username_match.group(1)
                if my_username and username.lower() == my_username.lower():
                    continue
                return href, username
    except:
        pass
        
    return None, None


def extract_active_chat_profile(browser):
    my_username = normalize_username(os.getenv("TIKTOK_USERNAME"))
    header_selectors = [
        "[data-e2e='chat-header']",
        "div[class*='DivChatHeader']",
        "div[class*='ChatHeader']",
        "[class*='ChatHeader']",
    ]

    for container_selector in header_selectors:
        try:
            containers = browser.find_elements(By.CSS_SELECTOR, container_selector)
        except Exception:
            continue
        for container in containers:
            try:
                if hasattr(container, "is_displayed") and not container.is_displayed():
                    continue
                links = container.find_elements(By.CSS_SELECTOR, "a[href*='/@']")
            except Exception:
                continue
            for link in links:
                try:
                    href = link.get_attribute("href")
                except Exception:
                    continue
                match = re.search(r"/@([^/?#]+)", href or "")
                if not match:
                    continue
                username = match.group(1)
                if normalize_username(username) == my_username:
                    continue
                return href, username

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
            # IDs found in page-wide scripts are not scoped to the active chat.
            # Never persist them because they can belong to another account.
            user_id, sec_uid = None, None
            
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
