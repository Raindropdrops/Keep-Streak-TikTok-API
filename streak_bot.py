"""
TikTok Streak Bot v2.0
=======================
Automatically sends streak reminder messages to specified TikTok contacts.
Upgraded with reliability features from TiktokStreakSaver.

Usage:
    python streak_bot.py --now                  # Send messages immediately
    python streak_bot.py --test                 # Test mode (find contacts but don't send)
    python streak_bot.py --now -m "Custom"      # Use custom message
    python streak_bot.py --interval             # Run on interval schedule
    python streak_bot.py --now --skip-cooldown  # Ignore daily cooldown
"""

import argparse
import json
import socket
import sys
import time
import logging
import os
from datetime import datetime, date
from DrissionPage import ChromiumPage, ChromiumOptions
import schedule
import requests

from config import (
    TIKTOK_MESSAGES_URL,
    STREAK_MESSAGE,
    SCHEDULE_TIME,
    SCHEDULE_INTERVAL_MINUTES,
    COOKIES_FILE,
    CONTACTS_FILE,
    RUN_HISTORY_FILE,
    LOGS_DIR,
    HEADLESS_MODE,
    USER_AGENT,
    PAGE_LOAD_WAIT,
    ELEMENT_WAIT,
    MESSAGE_SEND_DELAY,
    MAX_RETRIES_PER_CONTACT,
    SKIP_UNREACHABLE,
    DAILY_COOLDOWN,
    NETWORK_CHECK,
    LOG_FORMAT,
    LOG_DATE_FORMAT,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_ENABLED,
    TELEGRAM_LOG_ENABLED,
    TELEGRAM_LOG_LEVEL,
)


# =============================================================================
# Telegram Logging Handler
# =============================================================================

class TelegramHandler(logging.Handler):
    """Custom logging handler that sends log messages to Telegram."""
    
    def __init__(self):
        super().__init__()
        self.last_send_time = 0
        self.min_interval = 1  # Minimum 1 second between messages to avoid spam
        
    def emit(self, record):
        """Send log record to Telegram."""
        if not TELEGRAM_ENABLED or not TELEGRAM_LOG_ENABLED:
            return
        
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return
        
        try:
            # Rate limiting
            current_time = time.time()
            if current_time - self.last_send_time < self.min_interval:
                return
            
            # Format message with emoji based on log level
            emoji_map = {
                'DEBUG': '🔵',
                'INFO': 'ℹ️',
                'WARNING': '⚠️',
                'ERROR': '❌',
                'CRITICAL': '🚨'
            }
            
            emoji = emoji_map.get(record.levelname, '📝')
            timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
            
            # Format message
            message = f"{emoji} <b>{record.levelname}</b> [{timestamp}]\n{record.getMessage()}"
            
            # Send to Telegram
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            }
            
            requests.post(url, data=data, timeout=5)
            self.last_send_time = current_time
            
        except Exception:
            # Silently fail - don't want logging errors to crash the app
            pass


# Set up logging
def setup_logging():
    """Configure logging to file, console, and Telegram."""
    log_filename = os.path.join(LOGS_DIR, f"streak_bot_{datetime.now().strftime('%Y%m%d')}.log")
    
    # Create handlers list
    handlers = [
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
    
    # Add Telegram handler if enabled
    if TELEGRAM_ENABLED and TELEGRAM_LOG_ENABLED:
        telegram_handler = TelegramHandler()
        telegram_handler.setLevel(TELEGRAM_LOG_LEVEL)
        handlers.append(telegram_handler)
    
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=handlers
    )
    return logging.getLogger(__name__)


logger = setup_logging()


def send_telegram(message):
    """Send a message to Telegram."""
    if not TELEGRAM_ENABLED:
        return False
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.debug("Telegram not configured (missing token or chat_id)")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            logger.debug("Telegram notification sent successfully")
            return True
        else:
            logger.warning(f"Telegram API error: {response.status_code}")
            return False
            
    except Exception as e:
        logger.warning(f"Failed to send Telegram notification: {e}")
        return False


# =============================================================================
# Utility Functions
# =============================================================================

def check_network(timeout=5):
    """Check internet connectivity before starting browser."""
    try:
        socket.create_connection(("www.tiktok.com", 443), timeout=timeout)
        return True
    except OSError:
        return False


def load_contacts_data():
    """Load contacts with auto-migration from old string format."""
    if not os.path.exists(CONTACTS_FILE):
        return []
    try:
        with open(CONTACTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        contacts = data.get('contacts', [])
        if not contacts:
            return []
        # Auto-migrate old format: ["user1", "user2"] -> [{"username": "user1", ...}]
        if contacts and isinstance(contacts[0], str):
            migrated = []
            for c in contacts:
                migrated.append({
                    "username": c, "last_sent": None,
                    "success_count": 0, "failure_count": 0, "enabled": True
                })
            save_contacts_data(migrated)
            logger.info(f"Migrated {len(migrated)} contacts to enhanced format")
            return migrated
        return contacts
    except Exception as e:
        logger.error(f"Error loading contacts: {e}")
        return []


def save_contacts_data(contacts):
    """Save enhanced contacts data back to file."""
    try:
        with open(CONTACTS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"contacts": contacts}, f, indent=4, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error saving contacts: {e}")


def load_run_history():
    """Load run history from file."""
    if not os.path.exists(RUN_HISTORY_FILE):
        return []
    try:
        with open(RUN_HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def save_run_result(result):
    """Append a run result to history (max 50 entries)."""
    history = load_run_history()
    history.insert(0, result)
    history = history[:50]
    try:
        with open(RUN_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error saving run history: {e}")


class TikTokStreakBot:
    """Bot to automatically send streak messages on TikTok."""
    
    def __init__(self, headless=False, test_mode=False, custom_message=None, skip_cooldown=False):
        self.page = None
        self.headless = headless
        self.test_mode = test_mode
        self.custom_message = custom_message
        self.skip_cooldown = skip_cooldown
        self.contacts_data = []
        self.contacts_to_process = []
        self.target_usernames = []
        self.contacts_found = []
        self.results = {"sent": [], "failed": [], "skipped_cooldown": [], "not_found": []}
    
    def load_target_contacts(self):
        """Load contacts with daily cooldown filtering."""
        self.contacts_data = load_contacts_data()
        if not self.contacts_data:
            logger.error("No contacts found in contacts.json")
            return False

        today_str = date.today().isoformat()
        self.contacts_to_process = []

        for contact in self.contacts_data:
            username = contact.get('username', '')
            if not contact.get('enabled', True):
                continue
            # Daily cooldown check
            if DAILY_COOLDOWN and not self.skip_cooldown:
                last_sent = contact.get('last_sent')
                if last_sent and last_sent == today_str:
                    self.results['skipped_cooldown'].append(username)
                    logger.info(f"⏭️ Skipping {username} — already sent today")
                    continue
            self.contacts_to_process.append(contact)

        self.target_usernames = [c['username'] for c in self.contacts_to_process]
        logger.info(f"📋 {len(self.contacts_to_process)} to process, {len(self.results['skipped_cooldown'])} skipped (cooldown)")
        for u in self.target_usernames:
            logger.info(f"   - {u}")
        return len(self.contacts_to_process) > 0 or len(self.results['skipped_cooldown']) > 0
    
    def create_browser(self):
        """Create a ChromiumPage browser instance with anti-detection settings."""
        try:
            options = ChromiumOptions()
            
            # Anti-detection settings
            options.set_argument('--disable-blink-features=AutomationControlled')
            options.set_argument('--disable-infobars')
            options.set_argument('--disable-dev-shm-usage')
            options.set_argument('--no-sandbox')
            
            # Headless mode
            if self.headless:
                options.set_argument('--headless=new')
            
            options.set_user_agent(USER_AGENT)
            
            self.page = ChromiumPage(options)
            logger.info("Browser initialized successfully")
            return self.page
        except Exception as e:
            error_msg = f"Error creating browser: {e}"
            logger.error(error_msg)
            send_telegram(f"❌ <b>Browser Error</b>\n{error_msg}")
            raise
    
    def load_cookies(self):
        """Load cookies from file and apply to browser."""
        if not os.path.exists(COOKIES_FILE):
            logger.error(f"Cookies file not found: {COOKIES_FILE}")
            logger.error("Please export your TikTok cookies to cookies.json")
            return False
        
        try:
            with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            # Navigate to TikTok first (cookies need a domain)
            self.page.get("https://www.tiktok.com")
            time.sleep(2)
            
            # Add cookies
            for cookie in cookies:
                try:
                    self.page.set.cookies(cookie)
                except Exception as e:
                    logger.debug(f"Skipped cookie {cookie.get('name')}: {e}")
            
            logger.info(f"Loaded {len(cookies)} cookies")
            return True
            
        except Exception as e:
            error_msg = f"Error loading cookies: {e}"
            logger.error(error_msg)
            send_telegram(f"❌ <b>Cookie Error</b>\n{error_msg}")
            return False
    
    def verify_login(self):
        """Verify that we're logged in by checking the messages page."""
        try:
            self.page.get(TIKTOK_MESSAGES_URL)
            time.sleep(PAGE_LOAD_WAIT)
            
            current_url = self.page.url
            
            if 'login' in current_url:
                logger.error("Not logged in - redirected to login page")
                logger.error("Please run extract_cookies.py to refresh your cookies")
                return False
            
            if 'messages' in current_url:
                logger.info("✅ Login verified - on messages page")
                
                # Handle "Maybe later" popup if it appears (Passkey modal)
                try:
                    logger.info("Checking for popups...")
                    time.sleep(3)  # Wait for potential popup to appear
                    
                    # Strategy 1: Try to find and close passkey modal
                    # Using reverse engineering - detect modal by class and role attributes
                    logger.debug("Strategy 1: Detecting modal by TUXModal class...")
                    modal_detected = False
                    
                    try:
                        # Check if modal exists by class name
                        modal = self.page.ele('css:div[class*="TUXModal"]', timeout=2)
                        if modal:
                            logger.info("✅ Passkey modal detected!")
                            modal_detected = True
                    except:
                        logger.debug("No TUXModal found")
                    
                    # Also check by role=dialog
                    if not modal_detected:
                        try:
                            modal = self.page.ele('css:div[role="dialog"]', timeout=2)
                            if modal:
                                # Check if it contains passkey text
                                modal_text = modal.text.lower() if modal.text else ""
                                if "passkey" in modal_text or "create a passkey" in modal_text:
                                    logger.info("✅ Passkey dialog detected by role!")
                                    modal_detected = True
                        except:
                            logger.debug("No dialog modal found")
                    
                    # Strategy 2: If modal detected, find and click "Maybe later" button
                    if modal_detected:
                        logger.info("Attempting to dismiss passkey popup...")
                        
                        # Reverse engineered selectors based on actual TikTok DOM
                        maybe_later_selectors = [
                            # Exact class match for TikTok secondary button
                            'css:button.TUXButton--secondary',
                            'css:button.TUXButton.TUXButton--secondary',
                            
                            # Text-based (most reliable)
                            'xpath://button[.//div[contains(text(), "Maybe later")]]',
                            'xpath://button[contains(., "Maybe later")]',
                            'xpath://div[contains(@class, "TUXButton-label") and text()="Maybe later"]/ancestor::button',
                            
                            # Class combinations
                            'css:button[class*="TUXButton"][class*="secondary"]',
                            'css:button[class*="secondary"][aria-disabled="false"]',
                            
                            # Generic fallbacks
                            'xpath://button[contains(text(), "Maybe later")]',
                            'xpath://button[contains(text(), "maybe later")]',
                            'xpath://span[contains(text(), "Maybe later")]/parent::button',
                            'css:button[aria-label*="Maybe later"]',
                        ]
                        
                        dismissed = False
                        for selector in maybe_later_selectors:
                            try:
                                logger.debug(f"Trying selector: {selector}")
                                button = self.page.ele(selector, timeout=2)
                                if button:
                                    logger.info(f"✅ Found 'Maybe later' button with: {selector}")
                                    logger.debug("Clicking button...")
                                    
                                    # Try multiple click methods
                                    try:
                                        button.click()
                                        dismissed = True
                                    except:
                                        # Fallback to JS click
                                        logger.debug("Normal click failed, using JS click...")
                                        self.page.run_js("arguments[0].click();", button)
                                        dismissed = True
                                    
                                    time.sleep(1.5)
                                    logger.info("✅ Passkey popup dismissed successfully!")
                                    break
                            except Exception as e:
                                logger.debug(f"Selector {selector} failed: {e}")
                                continue
                        
                        if not dismissed:
                            logger.warning("⚠️ Modal detected but couldn't find dismiss button")
                    else:
                        logger.debug("No passkey modal detected - proceeding normally")
                    
                except Exception as e:
                    logger.debug(f"Popup handling error: {e}")
                
                return True
            
            logger.warning(f"Unexpected URL: {current_url}")
            return False
            
        except Exception as e:
            error_msg = f"Error verifying login: {e}"
            logger.error(error_msg)
            send_telegram(f"❌ <b>Login Verification Error</b>\n{error_msg}")
            return False
    
    def find_target_contacts(self):
        """Find and match contacts from the message list with target nicknames."""
        self.contacts_found = []
        
        try:
            # Wait for conversation list to load
            time.sleep(ELEMENT_WAIT + 3)
            
            logger.info("Searching for contacts using TikTok nickname elements...")
            
            # First, try to find nickname elements using the specific TikTok class
            nickname_selectors = [
                'css:p[class*="PInfoNickname"]',
                'css:p[class*="Nickname"]',
                'css:span[class*="Nickname"]',
                'css:div[class*="Nickname"]',
                'css:[data-e2e*="chat-list-item"] p',
                'css:[data-e2e*="chat-item"] p',
                'css:[data-e2e*="dm-new-conversation-item"] p',
            ]
            
            for target in self.target_usernames:
                found = False
                
                # Try each nickname selector
                for selector in nickname_selectors:
                    if found:
                        break
                    try:
                        nickname_elements = self.page.eles(selector)
                        logger.info(f"Found {len(nickname_elements)} elements with selector: {selector}")
                        
                        for elem in nickname_elements:
                            try:
                                elem_text = elem.text.strip() if elem.text else ""
                                logger.debug(f"  Checking nickname: '{elem_text}'")
                                
                                # Case-insensitive match
                                if elem_text.lower() == target.lower():
                                    # Find parent container to click
                                    parent = elem
                                    for _ in range(10):
                                        try:
                                            parent = parent.parent()
                                            if parent:
                                                parent_class = parent.attr('class') or ''
                                                # Look for conversation container
                                                if 'Item' in parent_class or 'item' in parent_class or 'Container' in parent_class:
                                                    self.contacts_found.append({
                                                        'element': parent,
                                                        'username': target,
                                                        'nickname_element': elem,
                                                        'index': len(self.contacts_found)
                                                    })
                                                    logger.info(f"✅ Found target contact: {target}")
                                                    found = True
                                                    break
                                        except Exception as e:
                                            logger.debug(f"Error finding parent: {e}")
                                            continue
                                    
                                    # If we couldn't find a good parent, use the element itself
                                    if not found:
                                        self.contacts_found.append({
                                            'element': elem,
                                            'username': target,
                                            'nickname_element': elem,
                                            'index': len(self.contacts_found)
                                        })
                                        logger.info(f"✅ Found target (using element directly): {target}")
                                        found = True
                                    break
                            except Exception as e:
                                logger.debug(f"Error checking element: {e}")
                                continue
                    except Exception as e:
                        logger.debug(f"Error with selector {selector}: {e}")
                        continue
                
                # If still not found, try text search
                if not found:
                    try:
                        elem = self.page.ele(f'xpath://*[text()="{target}"]')
                        if not elem:
                            elem = self.page.ele(f'xpath://*[contains(text(), "{target}")]')
                        
                        if elem:
                            self.contacts_found.append({
                                'element': elem,
                                'username': target,
                                'index': len(self.contacts_found)
                            })
                            logger.info(f"✅ Found via text search: {target}")
                    except:
                        pass
            
            # Report results
            found_usernames = {c['username'].lower() for c in self.contacts_found}
            not_found = [u for u in self.target_usernames if u.lower() not in found_usernames]
            
            if not_found:
                logger.warning(f"⚠️ Could not find these contacts: {', '.join(not_found)}")
                # Show available nicknames for debugging
                logger.info("Available nicknames on this page:")
                try:
                    for selector in nickname_selectors:
                        elements = self.page.eles(selector)
                        for elem in elements[:10]:
                            if elem.text:
                                logger.info(f"  - {elem.text.strip()}")
                except:
                    pass
            
            logger.info(f"📊 Found {len(self.contacts_found)}/{len(self.target_usernames)} target contacts")
            return self.contacts_found
            
        except Exception as e:
            error_msg = f"Error finding contacts: {e}"
            logger.error(error_msg)
            send_telegram(f"❌ <b>Contact Search Error</b>\n{error_msg}")
            return []
    
    def send_message(self, contact):
        """
        Send a streak message to a specific contact.
        Advanced version with retry mechanism and multiple strategies.
        
        Args:
            contact: Dictionary with contact info and element
        
        Returns:
            bool: True if message sent successfully
        """
        username = contact.get('username', 'Unknown')
        max_retries = MAX_RETRIES_PER_CONTACT
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"📤 Sending to: {username} (Attempt {attempt}/{max_retries})")
                
                # Strategy 1: Re-find by nickname with multiple selectors
                contact_element = self._find_contact_element(username)
                
                if not contact_element:
                    logger.warning(f"Strategy 1 failed for {username}, trying strategy 2...")
                    
                    # Strategy 2: Scroll and retry
                    self._scroll_messages_list()
                    time.sleep(1)
                    contact_element = self._find_contact_element(username)
                
                if not contact_element:
                    logger.warning(f"Strategy 2 failed for {username}, trying strategy 3...")
                    
                    # Strategy 3: Refresh message list and retry
                    self.page.refresh()
                    time.sleep(PAGE_LOAD_WAIT)
                    contact_element = self._find_contact_element(username)
                
                if not contact_element:
                    raise Exception(f"Could not find contact element after all strategies")
                
                # Click on the conversation to open it
                logger.debug(f"Clicking on contact: {username}")
                try:
                    contact_element.click()
                except:
                    # If click fails, try JS click
                    logger.debug("Normal click failed, trying JS click...")
                    self.page.run_js(f"arguments[0].click();", contact_element)
                
                time.sleep(ELEMENT_WAIT)
                
                # Find the message input field with multiple attempts
                input_field = self._find_message_input()
                
                if not input_field:
                    raise Exception(f"Could not find message input for {username}")
                
                # Click on input field to focus
                input_field.click()
                time.sleep(0.5)
                self.page.get_screenshot(path=os.path.join(LOGS_DIR, f"{username}_1_focus.jpg"))
                
                # Type the message
                message_to_send = self.custom_message if self.custom_message else STREAK_MESSAGE
                input_field.input(message_to_send)
                time.sleep(1)
                self.page.get_screenshot(path=os.path.join(LOGS_DIR, f"{username}_2_typed.jpg"))
                
                # Find and click send button, or press Enter
                send_button = self.page.ele('css:[data-e2e="chat-send"], [data-e2e="send-button"], svg[class*="send"], svg[class*="Send"]')
                
                if send_button:
                    logger.debug("Found send button, clicking it...")
                    send_button.click()
                else:
                    logger.debug("No send button found, pressing Enter...")
                    # Press Enter to send (use Keys.ENTER instead of literal \n)
                    from DrissionPage.common import Keys
                    input_field.input(Keys.ENTER)
                
                time.sleep(2)
                self.page.get_screenshot(path=os.path.join(LOGS_DIR, f"{username}_3_sent.jpg"))
                time.sleep(MESSAGE_SEND_DELAY - 2)
                
                logger.info(f"✅ Message sent to: {username}")
                return True
                
            except Exception as e:
                logger.warning(f"Attempt {attempt} failed for {username}: {e}")
                
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    # All retries exhausted
                    error_msg = f"Failed to send to {username} after {max_retries} attempts: {e}"
                    logger.error(error_msg)
                    send_telegram(f"❌ <b>Message Send Error</b>\nFailed to send to: {username}\nError: {str(e)}\nRetries: {max_retries}")
                    return False
        
        return False
    
    def _find_contact_element(self, username):
        """
        Find contact element by username with multiple strategies.
        
        Args:
            username: Contact username to find
            
        Returns:
            Element if found, None otherwise
        """
        logger.debug(f"Finding contact element for: {username}")
        
        # Try to find by nickname text
        nickname_selectors = [
            'css:p[class*="PInfoNickname"]',
            'css:p[class*="Nickname"]',
            'css:span[class*="Nickname"]',
            'css:div[class*="Nickname"]',
            'css:[data-e2e*="chat-list-item"] p',
            'css:[data-e2e*="chat-item"] p',
        ]
        
        for selector in nickname_selectors:
            try:
                elements = self.page.eles(selector)
                for elem in elements:
                    if elem.text and elem.text.strip().lower() == username.lower():
                        # Find parent container to click
                        parent = elem
                        for _ in range(10):
                            try:
                                parent = parent.parent()
                                if parent:
                                    parent_class = parent.attr('class') or ''
                                    if 'Item' in parent_class or 'item' in parent_class or 'Container' in parent_class:
                                        logger.debug(f"Found contact via selector: {selector}")
                                        return parent
                            except:
                                break
            except:
                continue
        
        # Fallback: Try xpath
        try:
            elem = self.page.ele(f'xpath://*[text()="{username}"]')
            if elem:
                logger.debug(f"Found contact via exact xpath")
                return elem
        except:
            pass
        
        try:
            elem = self.page.ele(f'xpath://*[contains(text(), "{username}")]')
            if elem:
                logger.debug(f"Found contact via contains xpath")
                return elem
        except:
            pass
        
        return None
    
    def _find_message_input(self):
        """
        Find message input field with multiple selectors.
        
        Returns:
            Input element if found, None otherwise
        """
        selectors = [
            'css:div[data-e2e="message-input"]',
            'css:div[contenteditable="true"]',
            'css:textarea[placeholder*="message"]',
            'css:input[placeholder*="message"]',
            'css:div[class*="Input"] div[contenteditable="true"]',
        ]
        
        for selector in selectors:
            try:
                elem = self.page.ele(selector, timeout=2)
                if elem:
                    logger.debug(f"Found input via: {selector}")
                    return elem
            except:
                continue
        
        return None
    
    def _scroll_messages_list(self):
        """Scroll the messages list to load more contacts."""
        try:
            logger.debug("Scrolling messages list...")
            self.page.run_js("window.scrollBy(0, -500);")
            time.sleep(0.5)
            self.page.run_js("window.scrollBy(0, 500);")
        except Exception as e:
            logger.debug(f"Scroll failed: {e}")
    
    def send_all_messages(self):
        """Send messages to all found contacts with per-contact tracking."""
        if not self.contacts_found:
            logger.info("No contacts to message")
            return 0
        
        success_count = 0
        
        for contact in self.contacts_found:
            username = contact.get('username', 'Unknown')
            if self.test_mode:
                logger.info(f"[TEST MODE] Would send to: {username}")
                self.results['sent'].append(username)
                success_count += 1
            else:
                if self.send_message(contact):
                    self.results['sent'].append(username)
                    # Update per-contact tracking
                    for c in self.contacts_data:
                        if c.get('username', '').lower() == username.lower():
                            c['last_sent'] = date.today().isoformat()
                            c['success_count'] = c.get('success_count', 0) + 1
                            break
                    save_contacts_data(self.contacts_data)
                    success_count += 1
                else:
                    self.results['failed'].append(username)
                    for c in self.contacts_data:
                        if c.get('username', '').lower() == username.lower():
                            c['failure_count'] = c.get('failure_count', 0) + 1
                            break
                    save_contacts_data(self.contacts_data)
                    if not SKIP_UNREACHABLE:
                        logger.error(f"Stopping: SKIP_UNREACHABLE is off and {username} failed")
                        break
            time.sleep(1)
        
        logger.info(f"📊 Sent {success_count}/{len(self.contacts_found)} messages")
        return success_count
    
    def run(self):
        """Main bot execution flow with enhanced tracking."""
        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info("🚀 TikTok Streak Bot v2.0 Starting")
        logger.info(f"⏰ Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        send_telegram("🚀 <b>TikTok Streak Bot v2.0 Started</b>\n⏰ " + start_time.strftime('%Y-%m-%d %H:%M:%S'))

        # Network check
        if NETWORK_CHECK and not check_network():
            msg = "No internet connection"
            logger.error(f"📡 {msg}")
            send_telegram(f"📡 <b>Offline</b>\n{msg}. Skipping this run.")
            save_run_result({"timestamp": start_time.isoformat(), "success": False, "error": msg, "sent": 0, "failed": 0, "skipped": 0})
            return False

        try:
            if not self.load_target_contacts():
                send_telegram("❌ <b>No Contacts</b>\ncontacts.json is empty or missing.")
                return False

            if not self.contacts_to_process:
                msg = f"All {len(self.results['skipped_cooldown'])} contacts already sent today"
                logger.info(f"⏭️ {msg}")
                send_telegram(f"⏭️ <b>All Skipped</b>\n{msg}")
                save_run_result({"timestamp": start_time.isoformat(), "success": True, "sent": 0, "failed": 0, "skipped": len(self.results['skipped_cooldown'])})
                return True

            self.create_browser()

            if not self.load_cookies():
                send_telegram("❌ <b>Cookie Error</b>\nFailed to load cookies. Please update cookies.json")
                return False

            if not self.verify_login():
                send_telegram("❌ <b>Login Failed</b>\nCookies may have expired.")
                return False

            self.find_target_contacts()

            not_found = [u for u in self.target_usernames if u.lower() not in {c['username'].lower() for c in self.contacts_found}]
            self.results['not_found'] = not_found

            if not self.contacts_found:
                send_telegram(f"⚠️ <b>No Contacts Found</b>\nCould not find any contacts in message list.")
                save_run_result({"timestamp": start_time.isoformat(), "success": False, "error": "No contacts found", "sent": 0, "failed": 0, "skipped": 0})
                return True

            self.send_all_messages()

            duration = int((datetime.now() - start_time).total_seconds())
            save_run_result({
                "timestamp": start_time.isoformat(),
                "success": len(self.results['failed']) == 0,
                "duration_seconds": duration,
                "sent": len(self.results['sent']),
                "failed": len(self.results['failed']),
                "skipped_cooldown": len(self.results['skipped_cooldown']),
                "not_found": len(self.results['not_found']),
                "details": self.results
            })

            # Enhanced Telegram summary
            lines = [f"{'✅' if not self.results['failed'] else '⚠️'} <b>Streak Run Complete!</b>\n"]
            lines.append(f"📊 <b>Sent:</b> {len(self.results['sent'])}/{len(self.contacts_found)}")
            if self.results['skipped_cooldown']:
                lines.append(f"⏭️ <b>Cooldown:</b> {len(self.results['skipped_cooldown'])}")
            if self.results['failed']:
                lines.append(f"❌ <b>Failed:</b> {', '.join(self.results['failed'])}")
            if self.results['not_found']:
                lines.append(f"🔍 <b>Not found:</b> {', '.join(self.results['not_found'])}")
            if self.results['sent']:
                lines.append(f"\n👥 <b>Sent to:</b>\n" + "\n".join(f"  • {u}" for u in self.results['sent']))
            lines.append(f"\n⏱️ Duration: {duration}s")
            send_telegram("\n".join(lines))

            return True

        except Exception as e:
            logger.error(f"Bot execution failed: {e}")
            send_telegram(f"❌ <b>Bot Error</b>\n{str(e)}")
            save_run_result({"timestamp": start_time.isoformat(), "success": False, "error": str(e), "sent": 0, "failed": 0, "skipped": 0})
            return False

        finally:
            if self.page:
                self.page.quit()
                logger.info("Browser closed")
    
    def close(self):
        """Close the browser."""
        if self.page:
            self.page.quit()


def run_scheduled_job(custom_message=None, skip_cooldown=False):
    """Job function for scheduled execution."""
    logger.info("⏰ Scheduled job triggered")
    bot = TikTokStreakBot(headless=HEADLESS_MODE, custom_message=custom_message, skip_cooldown=skip_cooldown)
    bot.run()


def main():
    """Main entry point with argparse CLI."""
    parser = argparse.ArgumentParser(
        description="🤖 TikTok Streak Bot v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  python streak_bot.py --now\n  python streak_bot.py --now -m \"Custom message\"\n  python streak_bot.py --interval\n  python streak_bot.py --now --skip-cooldown"
    )
    parser.add_argument('--now', action='store_true', help='Run bot immediately')
    parser.add_argument('--test', action='store_true', help='Test mode (find contacts, don\'t send)')
    parser.add_argument('-m', '--message', type=str, help='Custom message to send')
    parser.add_argument('--interval', action='store_true', help=f'Run on interval ({SCHEDULE_INTERVAL_MINUTES} min)')
    parser.add_argument('--skip-cooldown', action='store_true', help='Ignore daily cooldown check')
    args = parser.parse_args()

    if args.now:
        logger.info("Running bot immediately (--now)")
        bot = TikTokStreakBot(headless=HEADLESS_MODE, custom_message=args.message, skip_cooldown=args.skip_cooldown)
        bot.run()

    elif args.test:
        logger.info("Running in test mode (--test)")
        bot = TikTokStreakBot(headless=False, test_mode=True, custom_message=args.message)
        bot.run()

    elif args.interval:
        print("\n" + "=" * 60)
        print("🤖 TikTok Streak Bot v2.0 — Interval Mode")
        print("=" * 60)
        print(f"\n🔄 Running every {SCHEDULE_INTERVAL_MINUTES} minutes ({SCHEDULE_INTERVAL_MINUTES / 60:.1f} hours)")
        print(f"📝 Message: \"{args.message or STREAK_MESSAGE}\"")
        print(f"\n⏳ Press Ctrl+C to stop\n")
        print("=" * 60 + "\n")

        schedule.every(SCHEDULE_INTERVAL_MINUTES).minutes.do(run_scheduled_job, args.message, args.skip_cooldown)
        # Run immediately on first start
        run_scheduled_job(args.message, args.skip_cooldown)

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            print("\n👋 Bot stopped. Goodbye!")

    else:
        # Default: schedule daily at fixed time
        print("\n" + "=" * 60)
        print("🤖 TikTok Streak Bot v2.0")
        print("=" * 60)
        print(f"\n📅 Scheduled daily at: {SCHEDULE_TIME}")
        print(f"📝 Message: \"{args.message or STREAK_MESSAGE}\"")
        print(f"\n⏳ Waiting for scheduled time...")
        print("   Press Ctrl+C to stop\n")
        print("=" * 60 + "\n")

        schedule.every().day.at(SCHEDULE_TIME).do(run_scheduled_job, args.message, args.skip_cooldown)
        logger.info(f"Next run scheduled at: {SCHEDULE_TIME}")

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            print("\n👋 Bot stopped. Goodbye!")


if __name__ == "__main__":
    main()
