"""
Enhanced Cookie Manager for XHS Platform
Handles automatic cookie renewal with manual login assistance
"""

import json
import os
import time
from datetime import datetime, timedelta
from DrissionPage import Chromium, ChromiumOptions
from core import config
from utils.chromium_utils import get_chromium_options
from email_notifier import send_email


class XhsCookieManager:
    """Enhanced cookie manager with automatic renewal support"""
    
    def __init__(self, logger=None):
        self.logger = logger
        self.cookie_path = config.xhs_config["cookie_path"]
        self.login_url = "https://www.xiaohongshu.com/explore"
        self.upload_url = config.xhs_config["up_site"]
        
        # Get notification email from environment variable
        self.notification_email = os.getenv('NOTIFICATION_EMAIL', 'jack_hui@msn.com')
        if self.logger:
            self.logger.debug(f"Notification email set to: {self.notification_email}")
        
    def are_cookies_valid(self, tab):
        """Check if cookies are still valid by testing access to upload page"""
        try:
            tab.get(self.upload_url)
            tab.wait(3)
            
            # Check for login indicators
            if self._is_on_login_page(tab):
                return False
                
            # Check if upload button is accessible
            upload_button = tab.ele('tag:input@@class=upload-input@@type=file', timeout=5)
            return upload_button is not None
            
        except Exception as e:
            if self.logger:
                self.logger.debug(f"Cookie validation error: {e}")
            return False
    
    def _is_on_login_page(self, tab):
        """Detect if currently on login page"""
        try:
            current_url = tab.url.lower()
            login_indicators = [
                "login" in current_url,
                tab.ele('input[name="account"]', timeout=2),
                tab.ele('input[placeholder*="手机号"]', timeout=2),
                tab.ele('input[placeholder*="邮箱"]', timeout=2),
                tab.ele('.login-container', timeout=2)
            ]
            return any(login_indicators)
        except:
            return False
    
    def renew_cookies_with_manual_login(self, headless=False):
        """
        Open browser for manual login and automatically extract cookies
        Returns True if successful, False otherwise
        """
        if self.logger:
            self.logger.info("🔄 Starting cookie renewal process...")
            self.logger.info("📱 Opening browser for manual login - please log in manually")
        
        # Use mobile user agent for longer-lived cookies
        co = get_chromium_options(headless=False)  # Always visible for manual login
        co.set_user_agent('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1')
        
        browser = Chromium(co)
        tab = browser.latest_tab
        
        try:
            # Go to login page
            tab.get(self.login_url)
            tab.wait(2)
            
            if self.logger:
                self.logger.info("🔐 Please log in manually in the opened browser window")
                self.logger.info("⏳ Waiting for successful login...")
            
            # Wait for user to log in manually (check every 5 seconds)
            max_wait_minutes = 10
            start_time = time.time()
            
            while time.time() - start_time < max_wait_minutes * 60:
                if not self._is_on_login_page(tab):
                    # Try accessing upload page to confirm login
                    tab.get(self.upload_url)
                    tab.wait(3)
                    
                    if not self._is_on_login_page(tab):
                        # Successfully logged in, extract cookies
                        if self.logger:
                            self.logger.info("✅ Login successful! Extracting cookies...")
                        
                        cookies = tab.cookies()
                        self._save_cookies(cookies)
                        
                        if self.logger:
                            self.logger.info("💾 New cookies saved successfully")
                            self.logger.info("🔒 Browser session will remain open for a moment to establish session...")
                        
                        # Keep browser open briefly to establish session
                        tab.wait(5)
                        browser.quit()
                        return True
                
                time.sleep(5)  # Check every 5 seconds
            
            if self.logger:
                self.logger.error("⏰ Manual login timeout - please try again")
            browser.quit()
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ Cookie renewal failed: {e}")
            try:
                browser.quit()
            except:
                pass
            return False
    
    def _save_cookies(self, cookies):
        """Save cookies in the format expected by the uploader"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.cookie_path), exist_ok=True)
            
            # Format cookies for storage
            storage_state = {
                "cookies": cookies,
                "timestamp": datetime.now().isoformat(),
                "platform": "xhs"
            }
            
            with open(self.cookie_path, 'w', encoding='utf-8') as f:
                json.dump(storage_state, f, indent=2, ensure_ascii=False)
                
            if self.logger:
                self.logger.info(f"Cookies saved to: {self.cookie_path}")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save cookies: {e}")
            raise
    
    def load_cookies(self):
        """Load cookies from file"""
        try:
            if not os.path.exists(self.cookie_path):
                return None
                
            with open(self.cookie_path, 'r', encoding='utf-8') as f:
                storage_state = json.load(f)
                
            return storage_state.get('cookies', [])
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to load cookies: {e}")
            return None
    
    def get_cookie_age(self):
        """Get age of current cookies in hours"""
        try:
            if not os.path.exists(self.cookie_path):
                return float('inf')
                
            with open(self.cookie_path, 'r', encoding='utf-8') as f:
                storage_state = json.load(f)
                
            if 'timestamp' in storage_state:
                cookie_time = datetime.fromisoformat(storage_state['timestamp'])
                age = datetime.now() - cookie_time
                return age.total_seconds() / 3600  # Return hours
            
            # If no timestamp, check file modification time
            file_time = datetime.fromtimestamp(os.path.getmtime(self.cookie_path))
            age = datetime.now() - file_time
            return age.total_seconds() / 3600
            
        except:
            return float('inf')
    
    def send_cookie_expiry_notification(self, cookie_age_hours):
        """Send email notification when cookies are expired"""
        try:
            subject = "🔴 XHS Cookies Expired - Manual Login Required"
            body = f"""
The XHS (小红书) authentication cookies have expired and need manual renewal.

Cookie Details:
- Age: {cookie_age_hours:.1f} hours
- Expired at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Next scheduled run: Tonight at 9 PM

Action Required:
Please run the upload script before 9 PM tonight to perform manual login and renew the cookies.
The system will automatically open a browser window for you to log in manually.

Best regards,
YouTube Uploader System
            """
            
            send_email(subject, body, [self.notification_email])
            if self.logger:
                self.logger.info("📧 Cookie expiry notification email sent successfully")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ Failed to send cookie expiry notification: {e}")
    
    def check_and_notify_cookie_expiry(self, max_age_hours=48):
        """Check cookie age and send notification if expired"""
        cookie_age = self.get_cookie_age()
        
        if cookie_age > max_age_hours:
            if self.logger:
                self.logger.warning(f"⚠️ Cookies are {cookie_age:.1f} hours old (max: {max_age_hours}h)")
            self.send_cookie_expiry_notification(cookie_age)
            return True
        return False